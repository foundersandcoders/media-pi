#!/usr/bin/env bash

set -euo pipefail

# Resolve repo root so the script works regardless of CWD
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
cd "$REPO_ROOT"

# Load config and export
if [[ ! -f .env ]]; then
  echo "record.sh: .env not found — copy .env.example first" >&2
  exit 2 #(missing config)
fi
set -a
# shellcheck source=/dev/null
source .env
set +a

#set vars
PID_FILE="${PID_FILE:-/tmp/fac-recorder.pid}"
FILE_STATE="${PID_FILE}.file"
START_STATE="${PID_FILE}.started_at"
RECORDINGS_DIR="${RECORDINGS_DIR:-./recordings}"
LOG_DIR="${LOG_DIR:-./logs}"
DISK_SPACE_MIN_MB="${DISK_SPACE_MIN_MB:-500}"
# Seconds per segment before ffmpeg rotates to the next file. The daemon uploads
# each finished segment while the next records. On the Pi (VIDEO_CODEC=copy) the
# real length rounds up to the camera's next keyframe — see docs/dev/PLAN-1.md.
SEGMENT_DURATION="${SEGMENT_DURATION:-600}"

is_running() {
  [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

clear_state() {
  # removes all file states
  rm -f "$PID_FILE" "$FILE_STATE" "$START_STATE"
}

cmd_start() {
  if is_running; then
    echo "record.sh: already recording (pid $(cat "$PID_FILE"), file $(cat "$FILE_STATE" 2>/dev/null))" >&2
    exit 1
  fi

  # Stale state from a crashed run: clean up before checking disk.
  clear_state

  # Create dirs first so disk-full check can always find a valid path.
  mkdir -p "$RECORDINGS_DIR" "$LOG_DIR"

  # Disk-full guard. `|| true` prevents pipefail from killing the script.
  local avail_mb
  avail_mb=$(df -m "$RECORDINGS_DIR" 2>/dev/null | awk 'NR==2 {print $4}' || true)
  if [[ -z "$avail_mb" ]]; then
    avail_mb=$(df -m . | awk 'NR==2 {print $4}' || true)
  fi
  if [[ -n "$avail_mb" ]] && ((avail_mb < DISK_SPACE_MIN_MB)); then
    echo "record.sh: only ${avail_mb}MB free, need ${DISK_SPACE_MIN_MB}MB minimum" >&2
    exit 3
  fi

  local ts prefix pattern logfile
  ts=$(date +%Y%m%d_%H%M%S)
  # ffmpeg's segment muxer fills %03d with a 0-based index: session_<ts>_000.mp4,
  # _001.mp4, … The daemon globs `prefix*` to find segments and picks the part
  # number off the suffix; the highest index is the one still being written.
  prefix="${RECORDINGS_DIR%/}/session_${ts}_"
  pattern="${prefix}%03d.mp4"
  logfile="${LOG_DIR%/}/session_${ts}.log"

  # Video codec is platform config (.env), same pattern as FFMPEG_INPUT_ARGS:
  #   VIDEO_CODEC=copy (Pi) — mux the camera's onboard H.264 straight through.
  #     The Pi 5 has no hardware encoder; libx264 can't hold 1080p30 realtime
  #     (speed ~0.93x), and a live source that falls behind starves the audio
  #     input — heard as laggy, in-and-out sound.
  #   VIDEO_CODEC unset (Mac dev) — libx264-encode the raw avfoundation frames.
  # With -c:v copy ffmpeg can't insert keyframes, so the segment muxer cuts at the
  # camera's next existing keyframe at/after segment_time. On the libx264 dev path
  # we force a keyframe every segment so cuts land on time and each segment opens
  # on an I-frame (independently playable).
  local video_args
  if [[ "${VIDEO_CODEC:-libx264}" == "copy" ]]; then
    video_args=(-c:v copy)
  else
    video_args=(-c:v libx264 -preset veryfast -crf 23
      -force_key_frames "expr:gte(t,n_forced*${SEGMENT_DURATION})")
  fi

  # ffmpeg: input flags come from .env, audio is fixed (AAC).
  # We do NOT quote $FFMPEG_INPUT_ARGS — it contains multiple tokens that must
  # be split into separate argv entries.
  # nohup + background + PID capture is the idiomatic way to own a long-running
  # subprocess from a short-lived script.
  # The segment muxer rotates output every SEGMENT_DURATION seconds. Audio (AAC)
  # is re-encoded so it cuts cleanly anywhere; only the copied/encoded video gates
  # the boundary. movflags is carried *per segment* via segment_format_options so
  # the in-progress last segment is playable without a moov atom — a crash mid-
  # segment still leaves a usable file. -reset_timestamps makes each segment start
  # at PTS 0 so it plays standalone.
  # Known ffmpeg quirk: the FIRST segment is ~2x SEGMENT_DURATION (the muxer skips
  # the first boundary); every segment after it is exact. Harmless — all segments
  # are valid and upload independently.
  # shellcheck disable=SC2086
  nohup ffmpeg -hide_banner -nostdin -y \
    $FFMPEG_INPUT_ARGS \
    "${video_args[@]}" \
    -c:a aac \
    -f segment \
    -segment_time "$SEGMENT_DURATION" \
    -segment_format mp4 \
    -segment_format_options movflags=+frag_keyframe+empty_moov \
    -reset_timestamps 1 \
    "$pattern" >/dev/null 2>"$logfile" &

  local pid=$!
  echo "$pid" >"$PID_FILE"
  # FILE_STATE holds the session *prefix*, not a single filename — ffmpeg owns the
  # per-segment names. The daemon globs it to find the active (newest) segment.
  echo "$prefix" >"$FILE_STATE"
  date -u +%s >"$START_STATE"

  # Give ffmpeg a moment to fail fast (bad device, perms, etc) so we surface
  # the error instead of reporting "recording" for a process that just died.
  sleep 0.5
  if ! is_running; then
    echo "record.sh: ffmpeg exited immediately — see $logfile" >&2
    tail -5 "$logfile" >&2 || true
    clear_state
    exit 4
  fi

  # No DB row is created here. record.sh only knows the %03d pattern, not the
  # individual segment names ffmpeg picks — so the daemon's watcher owns row
  # creation, INSERTing one row per segment as each file appears (it sees the
  # active segment and creates a 'recording' row; finished segments flip to
  # in_queue). Python remains the sole DB writer; bash never touches SQLite.

  echo "recording pid=$pid session=$prefix"
}

cmd_stop() {
  if ! is_running; then
    echo "record.sh: not currently recording" >&2
    # Still echo the last filename if we have one, so callers can pipe to upload
    [[ -f "$FILE_STATE" ]] && cat "$FILE_STATE"
    clear_state
    exit 1
  fi

  local pid file
  pid=$(cat "$PID_FILE")
  file=$(cat "$FILE_STATE")

  # SIGINT (not SIGKILL). ffmpeg uses this to finalise the mp4 — writing the
  # `moov` atom with chunk offsets. Without it, the file is unplayable.
  kill -INT "$pid"

  # Bounded wait for graceful exit. 10s is generous for the finalise step.
  local waited=0
  while kill -0 "$pid" 2>/dev/null; do
    ((waited >= 10)) && break
    sleep 0.5
    waited=$((waited + 1))
  done

  if kill -0 "$pid" 2>/dev/null; then
    echo "record.sh: ffmpeg did not exit within 10s, escalating to SIGTERM" >&2
    kill -TERM "$pid" || true
    sleep 2
  fi

  clear_state
  echo "$file"
}

cmd_status() {
  if is_running; then
    local pid session started_at
    pid=$(cat "$PID_FILE")
    session=$(cat "$FILE_STATE" 2>/dev/null || echo "<unknown>")
    started_at=$(cat "$START_STATE" 2>/dev/null || echo "0")
    local elapsed=$(($(date -u +%s) - started_at))
    echo "recording pid=$pid session=$session elapsed=${elapsed}s"
  else
    # If PID file exists but process died, clean up so `start` works next.
    [[ -f "$PID_FILE" ]] && clear_state
    echo "idle"
  fi
}

cmd_last() {
  if [[ -f "$FILE_STATE" ]]; then
    cat "$FILE_STATE"
  else
    echo "record.sh: no session state — nothing to report" >&2
    exit 1
  fi
}

case "${1:-}" in
start) cmd_start ;;
stop) cmd_stop ;;
status) cmd_status ;;
last) cmd_last ;;
*)
  echo "usage: $0 {start|stop|status|last}" >&2
  exit 2
  ;;
esac

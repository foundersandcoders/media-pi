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
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# chunk being edited — scaffold, remove on implementation
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# TODO (Plan 2): scheduled-recording state, written by cmd_start when the
# daemon's scheduler launches a recording, read by cmd_status so the TUI can guard
# manual stops. New files alongside the three above:
#   SCHEDULED_STATE="${PID_FILE}.scheduled"   # presence = scheduled, not ad-hoc
#   END_TIME_STATE="${PID_FILE}.end_time"     # snapshot iso end_time for the prompt
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
RECORDINGS_DIR="${RECORDINGS_DIR:-./recordings}"
LOG_DIR="${LOG_DIR:-./logs}"
DISK_SPACE_MIN_MB="${DISK_SPACE_MIN_MB:-500}"

SEGMENT_FRAMES="${SEGMENT_FRAMES:-24000}"
VIDEO_FPS="${VIDEO_FPS:-30}"
MAX_SESSION_HOURS="${MAX_SESSION_HOURS:-12}"

is_running() {
  [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

clear_state() {
  # removes all file states
  # !!!! TODO (Plan 2): also rm -f "$SCHEDULED_STATE" "$END_TIME_STATE"
  rm -f "$PID_FILE" "$FILE_STATE" "$START_STATE"
}

cmd_start() {
  # !!!! TODO (Plan 2): parse optional `--scheduled --end-time <iso>` and write
  # SCHEDULED_STATE + END_TIME_STATE, so a daemon-scheduled recording is tagged.
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

  # We re-encode with libx264 (DR-001)
  local video_args split_list max_frames
  max_frames=$((MAX_SESSION_HOURS * 3600 * VIDEO_FPS))
  split_list=$(seq -s, "$SEGMENT_FRAMES" "$SEGMENT_FRAMES" "$max_frames")
  split_list="${split_list%,}" # BSD seq (macOS) appends a trailing separator; GNU does not
  video_args=(-c:v libx264 -preset veryfast -crf 23 -r "$VIDEO_FPS"
    -force_key_frames "expr:gte(n,n_forced*${SEGMENT_FRAMES})")

  # ffmpeg: input flags come from .env, audio is fixed (AAC, capped at 128k).
  # We do NOT quote $FFMPEG_INPUT_ARGS — it contains multiple tokens that must
  # be split into separate argv entries.
  # nohup + background + PID capture is the idiomatic way to own a long-running
  # subprocess from a short-lived script.
  #
  # The segment muxer splits at each frame number
  # shellcheck disable=SC2086
  nohup ffmpeg -hide_banner -nostdin -y \
    $FFMPEG_INPUT_ARGS \
    "${video_args[@]}" \
    -c:a aac -b:a 128k \
    -f segment \
    -segment_frames "$split_list" \
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
    # !!!! TODO (Plan 2): append `scheduled=<0|1> end_time=<iso>` so the TUI can
    # tell scheduled from ad-hoc and show the end time in the confirm prompt.
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

#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
cd "$REPO_ROOT"

if [[ ! -f .env ]]; then
  echo "upload-cdn.sh: .env not found — copy .env.example first" >&2
  exit 1
fi
set -a
# shellcheck source=/dev/null
source .env
set +a

: "${FAC_API_URL:?FAC_API_URL not set in .env}"
: "${FAC_API_KEY:?FAC_API_KEY not set in .env}"
LOG_DIR="${LOG_DIR:-./logs}"
PID_FILE="${PID_FILE:-/tmp/fac-recorder.pid}"

if ! command -v jq >/dev/null 2>&1; then
  echo "upload.sh: jq not found — install it (apt install jq)" >&2
  exit 1
fi

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <file>" >&2
  exit 1
fi
FILE="$1"

if [[ ! -f "$FILE" ]]; then
  echo "upload-cdn.sh: file not found: $FILE" >&2
  exit 2
fi
if [[ ! -s "$FILE" ]]; then
  echo "upload-cdn.sh: file is empty: $FILE" >&2
  exit 2
fi

# If record.sh is still writing this file, refuse.
if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  current_file=$(cat "${PID_FILE}.file" 2>/dev/null || true)
  if [[ "$current_file" == "$FILE" ]]; then
    echo "upload-cdn.sh: $FILE is currently being recorded — stop first" >&2
    exit 2
  fi
fi

mkdir -p "$LOG_DIR"
LOGFILE="${LOG_DIR%/}/upload_$(basename "${FILE%.*}").log"

log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOGFILE" >&2
}

EXT="${FILE##*.}"
EXT_LC=$(echo "$EXT" | tr '[:upper:]' '[:lower:]')

# --- 1. register ------------------------------------------------------------
log "register: POST $FAC_API_URL (ext=$EXT_LC)"

REGISTER_BODY=$(jq -nc --arg ext "$EXT_LC" '{
  source: "mutation WatchIngestRegister($ext:String!){ watch_ingest_register(ext:$ext) }",
  variableValues: { ext: $ext }
}')

REG=$(curl -fsS -X POST "$FAC_API_URL" \
  -H "Authorization: Bearer $FAC_API_KEY" \
  -H "Content-Type: application/json" \
  --data "$REGISTER_BODY" 2>>"$LOGFILE") || {
  log "register: curl failed"
  exit 4
}

# The /g endpoint strips the GraphQL envelope (see fac-cra api/app.ts), so the
# resolver's { video_id, object_key } arrives at the top level.
VIDEO_ID=$(echo "$REG" | jq -r '.video_id // empty')
OBJECT_KEY=$(echo "$REG" | jq -r '.object_key // empty')
UPLOAD_URL=$(echo "$REG" | jq -r '.upload_url // empty')

if [[ -z "$VIDEO_ID" || -z "$OBJECT_KEY" || -z "$UPLOAD_URL" ]]; then
  log "register: bad response — $REG"
  exit 4
fi
log "register: video_id=$VIDEO_ID object_key=$OBJECT_KEY"

# --- 2. upload via presigned PUT (direct to CDN) ----------------------------
# register returns a presigned S3 URL (SignedHeaders=host), so the Pi needs no
# storage credentials. curl streams the file from disk and retries the whole PUT
# on transient errors. A presigned PUT is single-shot — no resume — so a hard
# failure re-uploads from scratch; the daemon/TUI retry is the outer safety net.
# `?` is stripped from the logged URL to keep the signature out of the logs.
log "upload: PUT → ${UPLOAD_URL%%\?*}"
rc=0
curl -fsS --upload-file "$FILE" "$UPLOAD_URL" \
  -H "Content-Type: video/mp4" \
  --retry 5 \
  --retry-delay 10 \
  --retry-all-errors \
  >>"$LOGFILE" 2>&1 || rc=$?
if ((rc != 0)); then
  log "upload: PUT failed (rc=$rc) — see $LOGFILE"
  echo "${FILE}.failed: upload failed rc=$rc at $(date -u +%Y-%m-%dT%H:%M:%SZ) video_id=$VIDEO_ID object_key=$OBJECT_KEY" >"${FILE}.failed"
  exit 3
fi
log "upload: ok"

# --- 3. confirm -------------------------------------------------------------
log "confirm: POST $FAC_API_URL"

CONFIRM_BODY=$(jq -nc --arg id "$VIDEO_ID" --arg k "$OBJECT_KEY" '{
  source: "mutation WatchIngestConfirm($id:ID!,$k:String!){ watch_ingest_confirm(video_id:$id,object_key:$k) }",
  variableValues: { id: $id, k: $k }
}')

CONFIRM=$(curl -fsS -X POST "$FAC_API_URL" \
  -H "Authorization: Bearer $FAC_API_KEY" \
  -H "Content-Type: application/json" \
  --data "$CONFIRM_BODY" 2>>"$LOGFILE") || {
  log "confirm: curl failed — leaving $FILE in place for manual retry"
  echo "${FILE}.failed: confirm failed at $(date -u +%Y-%m-%dT%H:%M:%SZ) video_id=$VIDEO_ID object_key=$OBJECT_KEY" >"${FILE}.failed"
  exit 5
}

log "confirm: ok ($CONFIRM) — deleting local $FILE"
rm -f "$FILE"
log "done"

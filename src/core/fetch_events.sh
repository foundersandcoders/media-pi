#!/usr/bin/env bash

# &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&
# new file — scaffold, remove on implementation
# &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&

# Fetch the Pi's lesson schedule from the FAC server. Mirrors upload.sh —
# sources .env for auth, curls the REST endpoint, prints the JSON array to stdout.
# The daemon's poller (pipeline._fetch_events) parses the output.
#
# usage: fetch_events.sh <from_iso> <to_iso>
#
# STUB (Plan 1): real curl + arg handling lands in Plan 2. Echoes fake data so the
# walking skeleton runs without a live server.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
cd "$REPO_ROOT"

# TODO (Plan 2): load .env and require the schedule config, mirroring upload.sh:13-19
#   set -a; source .env; set +a
#   : "${FAC_SCHEDULE_URL:?FAC_SCHEDULE_URL not set in .env}"
#   : "${FAC_SCHEDULE_KEY:?FAC_SCHEDULE_KEY not set in .env}"

# TODO (Plan 2): GET the window and print the JSON array; exit non-zero on failure
#   curl -fsS -H "Authorization: Bearer $FAC_SCHEDULE_KEY" \
#     "${FAC_SCHEDULE_URL}?from=${1}&to=${2}"

# Fake walking-skeleton output (one workshop + one cohort event; `type` discriminates,
# name = group key, title = per-occurrence label):
echo '[{"remote_id":"fake:workshop:1","type":"workshop","name":"Fake Workshop","title":"Fake Workshop","start_time":"2026-06-30T13:00:00Z","end_time":"2026-06-30T15:00:00Z"},{"remote_id":"fake:cohort:1","type":"cohort","name":"FAC30","title":"Week 3 - Fake Lesson","start_time":"2026-06-30T10:00:00Z","end_time":"2026-06-30T17:00:00Z"}]'

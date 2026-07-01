#!/usr/bin/env bash

# Fetch the Pi's lesson schedule from the FAC server. Mirrors upload.sh — sources
# .env for auth, curls the REST endpoint, prints the JSON array to stdout. The
# daemon's poller (pipeline._fetch_events) parses the output.
#
# usage: fetch_events.sh <from_iso> <to_iso>

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
cd "$REPO_ROOT"

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <from_iso> <to_iso>" >&2
  exit 1
fi
FROM="$1"
TO="$2"

if [[ ! -f .env ]]; then
  echo "fetch_events.sh: .env not found — copy .env.example first" >&2
  exit 1
fi
set -a
# shellcheck source=/dev/null
source .env
set +a

: "${FAC_SCHEDULE_URL:?FAC_SCHEDULE_URL not set in .env}"
: "${FAC_SCHEDULE_KEY:?FAC_SCHEDULE_KEY not set in .env}"

# GET the window; --get + --data-urlencode builds ?from=..&to=.. with proper
# escaping. -f makes curl exit non-zero on HTTP errors so the daemon sees a
# failed poll. The server returns a JSON array of ServerEvents (may be []).
curl -fsS --get "$FAC_SCHEDULE_URL" \
  -H "Authorization: Bearer $FAC_SCHEDULE_KEY" \
  --data-urlencode "from=${FROM}" \
  --data-urlencode "to=${TO}"

"""Create the video row when a recording starts.

Invoked by record.sh immediately after ffmpeg is confirmed running:

    PYTHONPATH=src python3 -m daemon.record_start <file_path>

This is the INSERT half of the UPDATE-only pipeline (see docs/daemon.md): the row
is born at status='recording', and the daemon later transitions it as the file
moves through upload. Row creation is best-effort — record.sh ignores our exit
code, so a DB hiccup never stops a recording.

Sole DB writer principle (docs/dev/error-handling.md): bash shells out to us; it
never touches SQLite itself.
"""

import sys
from datetime import datetime

from .db import find_video_by_path, get_connection, load_status_ids

# All recordings are attributed to this single cohort until event/schedule
# resolution lands. To replace the hack, swap this constant for real resolution
# and delete _get_or_create_cohort below.
TEMP_COHORT_NAME = "FACM9"  # temp hardcoded value


def _get_or_create_cohort(conn, name: str) -> int:
    """Return the id of the cohort named `name`, creating it if absent.

    cohort_mapping.name has no UNIQUE constraint, so we SELECT-then-INSERT rather
    than INSERT OR IGNORE. The date/time fields are NOT NULL; this placeholder
    cohort fills them with obvious sentinels so it reads as a stand-in at a glance.
    """
    row = conn.execute(
        "SELECT id FROM cohort_mapping WHERE name=?",
        (name,),
    ).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO cohort_mapping"
        " (name, start_date, end_date, session_start_time, session_end_time)"
        " VALUES (?, ?, ?, ?, ?)",
        (name, "1970-01-01", "1970-01-01", "00:00", "00:00"),  # temp placeholder
    )
    return cur.lastrowid


def record_start(path: str) -> None:
    """INSERT a video row (status='recording') for a freshly started recording."""
    conn = get_connection()
    try:
        if find_video_by_path(conn, path) is not None:
            return  # idempotent: a row already exists for this file
        cohort_id = _get_or_create_cohort(conn, TEMP_COHORT_NAME)
        status_id = load_status_ids(conn)["recording"]
        conn.execute(
            "INSERT INTO video"
            " (file_path, cohort_mapping_id, workshop_mapping_id, recorded_at,"
            "  status_mapping_id, part)"
            " VALUES (?, ?, NULL, ?, ?, 1)",
            (path, cohort_id, datetime.now().isoformat(timespec="seconds"), status_id),
        )
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python -m daemon.record_start <file_path>", file=sys.stderr)
        raise SystemExit(2)
    record_start(sys.argv[1])


if __name__ == "__main__":
    main()

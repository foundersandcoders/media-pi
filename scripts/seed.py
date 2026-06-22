#!/usr/bin/env python3
"""Populates the test database with representative seed data. Test DB only."""
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tui.db import get_connection, get_db_path, init_schema

db_path = get_db_path()
if "test" not in db_path.name:
    print(f"seed.py: refusing to seed {db_path} — test DB only", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

COHORTS = [
    {
        "name": "FAC30",
        "start_date": (date.today() - timedelta(weeks=12)).isoformat(),
        "end_date": (date.today() + timedelta(weeks=12)).isoformat(),
        "session_start_time": "10:00",
        "session_end_time": "17:00",
    },
    {
        "name": "FAC29",
        "start_date": (date.today() - timedelta(weeks=36)).isoformat(),
        "end_date": (date.today() - timedelta(weeks=12)).isoformat(),
        "session_start_time": "10:00",
        "session_end_time": "17:00",
    },
]

WORKSHOPS = [
    {"name": "Intro to SQL"},
    {"name": "Auth week"},
    {"name": "Testing fundamentals"},
    {"name": "Accessibility"},
]


def _dt(d: date, t: time) -> str:
    return datetime.combine(d, t).isoformat()


def _error_id(conn, exit_code, error_id):
    row = conn.execute(
        "SELECT id FROM error_mapping WHERE exit_code=? AND error_id=?",
        (exit_code, error_id),
    ).fetchone()
    return row["id"] if row else None


def seed(conn):
    # cohort_mapping
    cohort_ids = []
    for c in COHORTS:
        cur = conn.execute(
            "INSERT INTO cohort_mapping (name, start_date, end_date, session_start_time, session_end_time)"
            " VALUES (:name, :start_date, :end_date, :session_start_time, :session_end_time)",
            c,
        )
        cohort_ids.append(cur.lastrowid)

    # workshop_mapping
    workshop_ids = []
    for w in WORKSHOPS:
        cur = conn.execute("INSERT INTO workshop_mapping (name) VALUES (:name)", w)
        workshop_ids.append(cur.lastrowid)

    # events — prefill weekly sessions for active cohort (FAC30)
    active_cohort_id = cohort_ids[0]
    active = COHORTS[0]
    session_start = time.fromisoformat(active["session_start_time"])
    session_end = time.fromisoformat(active["session_end_time"])
    d = date.fromisoformat(active["start_date"])
    end = date.fromisoformat(active["end_date"])
    while d <= end:
        conn.execute(
            "INSERT INTO event (cohort_mapping_id, start_time, end_time) VALUES (?, ?, ?)",
            (active_cohort_id, _dt(d, session_start), _dt(d, session_end)),
        )
        d += timedelta(weeks=1)

    # events — two open workshop events
    conn.execute(
        "INSERT INTO event (workshop_mapping_id, start_time, end_time) VALUES (?, ?, ?)",
        (
            workshop_ids[0],
            _dt(date.today() + timedelta(days=3), time(10, 0)),
            _dt(date.today() + timedelta(days=3), time(13, 0)),
        ),
    )
    conn.execute(
        "INSERT INTO event (workshop_mapping_id, start_time, end_time) VALUES (?, ?, ?)",
        (
            workshop_ids[1],
            _dt(date.today() + timedelta(days=10), time(14, 0)),
            _dt(date.today() + timedelta(days=10), time(17, 0)),
        ),
    )

    # videos — mix of statuses, cohort and workshop
    videos = [
        {
            "file_path": "/opt/media-pi/recordings/session_20260601_100000.mp4",
            "cohort_mapping_id": active_cohort_id,
            "workshop_mapping_id": None,
            "recorded_at": _dt(date.today() - timedelta(weeks=3), time(10, 0)),
            "video_size": 1_200_000_000,
            "video_length": 25200,
            "status": "uploaded",
            "part": 1,
            "error_mapping_id": None,
        },
        {
            "file_path": "/opt/media-pi/recordings/session_20260601_170000.mp4",
            "cohort_mapping_id": active_cohort_id,
            "workshop_mapping_id": None,
            "recorded_at": _dt(date.today() - timedelta(weeks=3), time(17, 0)),
            "video_size": 800_000_000,
            "video_length": 14400,
            "status": "uploaded",
            "part": 2,
            "error_mapping_id": None,
        },
        {
            "file_path": "/opt/media-pi/recordings/session_20260608_100000.mp4",
            "cohort_mapping_id": active_cohort_id,
            "workshop_mapping_id": None,
            "recorded_at": _dt(date.today() - timedelta(weeks=2), time(10, 0)),
            "video_size": 950_000_000,
            "video_length": 18000,
            "status": "failed",
            "part": 1,
            "error_mapping_id": _error_id(conn, 5, 1),
        },
        {
            "file_path": "/opt/media-pi/recordings/session_20260615_100000.mp4",
            "cohort_mapping_id": active_cohort_id,
            "workshop_mapping_id": None,
            "recorded_at": _dt(date.today() - timedelta(weeks=1), time(10, 0)),
            "video_size": None,
            "video_length": None,
            "status": "pending",
            "part": 1,
            "error_mapping_id": None,
        },
        {
            "file_path": "/opt/media-pi/recordings/workshop_sql_20260610_100000.mp4",
            "cohort_mapping_id": None,
            "workshop_mapping_id": workshop_ids[0],
            "recorded_at": _dt(date.today() - timedelta(days=5), time(10, 0)),
            "video_size": 600_000_000,
            "video_length": 10800,
            "status": "uploaded",
            "part": 1,
            "error_mapping_id": None,
        },
    ]
    for v in videos:
        conn.execute(
            "INSERT INTO video"
            " (file_path, cohort_mapping_id, workshop_mapping_id, recorded_at,"
            "  video_size, video_length, status, part, error_mapping_id)"
            " VALUES (:file_path, :cohort_mapping_id, :workshop_mapping_id, :recorded_at,"
            "  :video_size, :video_length, :status, :part, :error_mapping_id)",
            v,
        )


if __name__ == "__main__":
    print(f"Seeding {db_path}")
    with get_connection() as conn:
        init_schema(conn)
        seed(conn)
    print("Done.")

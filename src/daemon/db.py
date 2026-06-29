"""Database helpers for the daemon.

Reuses the TUI's connection factory (tui.db.get_connection) so both processes
share the same DB path resolution and PRAGMAs (foreign_keys + WAL). The daemon
runs single-threaded under asyncio, so one connection is held for its lifetime;
queries are local and fast enough to run inline on the event loop.
"""

import os
import re
import sqlite3
from datetime import datetime

from tui.db import (  # noqa: F401 — re-exported for the daemon
    get_connection,
    notify_change,
)

# Where record.sh writes segments; the watcher and helpers resolve paths against
# this. Single definition — pipeline.py imports it from here.
RECORDINGS_DIR = os.environ.get("RECORDINGS_DIR", "./recordings")

# All recordings are attributed to this single cohort until event/schedule
# resolution lands. Replace the constant (and the SELECT-then-INSERT below) with
# real resolution when it arrives.
TEMP_COHORT_NAME = "FACM9"  # temp hardcoded value

# Segment files are named session_<ts>_NNN.mp4 by ffmpeg's segment muxer.
_SEGMENT_RE = re.compile(r"_(\d+)\.mp4$")


def segment_part(path: str) -> int | None:
    """Part number for a segment file, or None if `path` is not a segment.

    ffmpeg's %03d index is 0-based; video.part is 1-based (schema DEFAULT 1), so
    session_..._000.mp4 -> part 1, _001 -> 2. Single source of truth for the
    mapping, shared by the watcher, active-segment detection, and tests.
    """
    match = _SEGMENT_RE.search(os.path.basename(path))
    return int(match.group(1)) + 1 if match else None


def load_status_ids(conn: sqlite3.Connection) -> dict[str, int]:
    """Load the whole status_mapping into {name: id} once at startup."""
    rows = conn.execute("SELECT id, name FROM status_mapping").fetchall()
    return {row["name"]: row["id"] for row in rows}


def get_or_create_cohort(conn: sqlite3.Connection, name: str = TEMP_COHORT_NAME) -> int:
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


def create_video_row(
    conn: sqlite3.Connection,
    ids: dict[str, int],
    path: str,
    part: int,
    status: str = "recording",
) -> int:
    """INSERT a video row for `path` if absent; return its id (existing or new).

    Idempotent via find_video_by_path, so the watcher can call it on every change
    event for the active segment without duplicating rows. The cohort is the temp
    placeholder; workshop is NULL, satisfying the schema's exactly-one CHECK.
    """
    existing = find_video_by_path(conn, path)
    if existing is not None:
        return existing["id"]
    cohort_id = get_or_create_cohort(conn)
    cur = conn.execute(
        "INSERT INTO video"
        " (file_path, cohort_mapping_id, workshop_mapping_id, recorded_at,"
        "  status_mapping_id, part)"
        " VALUES (?, ?, NULL, ?, ?, ?)",
        (
            path,
            cohort_id,
            datetime.now().isoformat(timespec="seconds"),
            ids[status],
            part,
        ),
    )
    conn.commit()
    notify_change()
    return cur.lastrowid


def find_video_by_path(conn: sqlite3.Connection, path: str) -> sqlite3.Row | None:
    """Find the video row whose file_path resolves to the same file as `path`.

    Paths are normalised with realpath so a relative stored path (record.sh
    defaults RECORDINGS_DIR to ./recordings) matches an absolute event path,
    provided both processes run from the repo root.
    """
    target = os.path.realpath(path)
    rows = conn.execute("SELECT id, file_path, status_mapping_id FROM video").fetchall()
    for row in rows:
        if os.path.realpath(row["file_path"]) == target:
            return row
    return None


def set_status(conn: sqlite3.Connection, video_id: int, status_id: int) -> None:
    """Transition a video row's status."""
    conn.execute(
        "UPDATE video SET status_mapping_id=? WHERE id=?",
        (status_id, video_id),
    )
    conn.commit()
    notify_change()


def recover_in_flight(conn: sqlite3.Connection, ids: dict[str, int]) -> int:
    """Reset rows stuck at 'uploading' (daemon died mid-upload) back to 'in_queue'.

    Returns the number of rows reset. We can't know whether the upload actually
    completed, so the safe choice is to re-queue and let upload.sh run again.
    """
    cur = conn.execute(
        "UPDATE video SET status_mapping_id=? WHERE status_mapping_id=?",
        (ids["in_queue"], ids["uploading"]),
    )
    conn.commit()
    if cur.rowcount:
        notify_change()
    return cur.rowcount


def recover_stranded_recordings(
    conn: sqlite3.Connection, ids: dict[str, int], active_path: str | None
) -> list[sqlite3.Row]:
    """Re-queue rows stuck at 'recording' whose file is finished.

    If the daemon was down (or restarting) when a recording stopped, the watcher
    never saw the finish event and the row is stranded at 'recording'. On startup
    we reconcile: a 'recording' row whose file exists on disk and is NOT the file
    record.sh is currently writing (`active_path`) is a finished segment — flip it
    to 'in_queue'. Rows whose file is missing, or which are still being recorded,
    are left untouched. Returns the rows re-queued.
    """
    recovered = []
    rows = conn.execute(
        "SELECT id, file_path FROM video WHERE status_mapping_id=?",
        (ids["recording"],),
    ).fetchall()
    for row in rows:
        real = os.path.realpath(row["file_path"])
        if active_path is not None and real == active_path:
            continue  # still being recorded
        if not os.path.exists(real):
            continue  # file gone — nothing to upload
        conn.execute(
            "UPDATE video SET status_mapping_id=? WHERE id=?",
            (ids["in_queue"], row["id"]),
        )
        recovered.append(row)
    conn.commit()
    if recovered:
        notify_change()
    return recovered


def pending_videos(conn: sqlite3.Connection, ids: dict[str, int]) -> list[sqlite3.Row]:
    """All rows currently 'in_queue' (id, file_path), oldest first."""
    return conn.execute(
        "SELECT id, file_path FROM video"
        " WHERE status_mapping_id=? ORDER BY recorded_at ASC",
        (ids["in_queue"],),
    ).fetchall()

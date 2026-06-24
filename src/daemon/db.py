"""Database helpers for the daemon.

Reuses the TUI's connection factory (tui.db.get_connection) so both processes
share the same DB path resolution and PRAGMAs (foreign_keys + WAL). The daemon
runs single-threaded under asyncio, so one connection is held for its lifetime;
queries are local and fast enough to run inline on the event loop.
"""

import os
import sqlite3

from tui.db import get_connection  # noqa: F401 — re-exported for the daemon


def load_status_ids(conn: sqlite3.Connection) -> dict[str, int]:
    """Load the whole status_mapping into {name: id} once at startup."""
    rows = conn.execute("SELECT id, name FROM status_mapping").fetchall()
    return {row["name"]: row["id"] for row in rows}


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
    return recovered


def pending_videos(conn: sqlite3.Connection, ids: dict[str, int]) -> list[sqlite3.Row]:
    """All rows currently 'in_queue' (id, file_path), oldest first."""
    return conn.execute(
        "SELECT id, file_path FROM video"
        " WHERE status_mapping_id=? ORDER BY recorded_at ASC",
        (ids["in_queue"],),
    ).fetchall()

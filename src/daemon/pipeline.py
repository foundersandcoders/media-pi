"""The upload pipeline coroutines.

watch_recordings(): inotify/FSEvents watch over the recordings dir. When a
finished .mp4 appears that maps to an existing video row, flip it to 'in_queue'
and hand it to the worker. UPDATE-only — rows are created at RECORD time.

upload_worker(): single sequential consumer. Runs upload.sh per file and writes
the outcome back to the DB. A `None` sentinel on the queue stops it cleanly
(after any in-flight upload finishes).
"""

import asyncio
import logging
import os

from tui.paths import UPLOAD

from .db import find_video_by_path, set_status

log = logging.getLogger("daemon.pipeline")

RECORDINGS_DIR = os.environ.get("RECORDINGS_DIR", "./recordings")
_PID_FILE = os.environ.get("PID_FILE", "/tmp/fac-recorder.pid")
_FILE_STATE = f"{_PID_FILE}.file"

# Sentinel pushed onto the queue to stop the worker after the current upload.
STOP = None


def active_recording_file() -> str | None:
    """Absolute path of the file record.sh is currently writing, if any."""
    try:
        with open(_FILE_STATE) as fh:
            path = fh.read().strip()
        return os.path.realpath(path) if path else None
    except FileNotFoundError:
        return None


async def watch_recordings(conn, ids, queue: asyncio.Queue, stop: asyncio.Event):
    """Watch the recordings dir; enqueue finished segments that have a row."""
    from watchfiles import awatch

    os.makedirs(RECORDINGS_DIR, exist_ok=True)
    log.info("watching %s for finished recordings", RECORDINGS_DIR)

    async for changes in awatch(RECORDINGS_DIR, stop_event=stop):
        active = active_recording_file()
        for _change, path in changes:
            if not path.endswith(".mp4"):
                continue
            if active is not None and os.path.realpath(path) == active:
                continue  # still being written by the recorder
            row = find_video_by_path(conn, path)
            if row is None:
                log.info("no video row for %s — skipping", path)
                continue
            if row["status_mapping_id"] not in (ids["recording"], ids["in_queue"]):
                continue  # already uploading / uploaded / failed
            set_status(conn, row["id"], ids["in_queue"])
            queue.put_nowait((row["id"], path))
            log.info("queued video id=%s %s", row["id"], path)

    log.info("watch_recordings stopped")


async def upload_worker(conn, ids, queue: asyncio.Queue):
    """Consume the queue one item at a time; upload and record the outcome."""
    log.info("upload worker started")
    while True:
        item = await queue.get()
        try:
            if item is STOP:
                break
            video_id, path = item
            set_status(conn, video_id, ids["uploading"])
            log.info("uploading video id=%s %s", video_id, path)

            proc = await asyncio.create_subprocess_exec(UPLOAD, path)
            rc = await proc.wait()

            # Generic handling for now — see docs/dev/error-handling.md for the
            # planned (exit_code, error_id) scheme.
            status_name = "uploaded" if rc == 0 else "failed"
            set_status(conn, video_id, ids[status_name])
            log.info("video id=%s -> %s (rc=%s)", video_id, status_name, rc)
        finally:
            queue.task_done()
    log.info("upload worker stopped")

"""The upload pipeline coroutines.

watch_recordings(): inotify/FSEvents watch over the recordings dir. ffmpeg's
segment muxer rotates to a new session_<ts>_NNN.mp4 every SEGMENT_DURATION
seconds; the newest segment is the one still being written, everything below it
is finished. The watcher owns the per-segment row lifecycle: it creates a
'recording' row for the active segment and flips finished segments to 'in_queue'
before handing them to the worker.

upload_worker(): single sequential consumer. Runs upload.sh per file and writes
the outcome back to the DB. A `None` sentinel on the queue stops it cleanly
(after any in-flight upload finishes).
"""

import asyncio
import glob
import logging
import os

from tui.paths import UPLOAD

from .db import (
    RECORDINGS_DIR,
    create_video_row,
    find_video_by_path,
    recover_stranded_recordings,
    segment_part,
    set_status,
    # &&&& new (scaffold)
    sync_events,
)

log = logging.getLogger("daemon.pipeline")

_PID_FILE = os.environ.get("PID_FILE", "/tmp/fac-recorder.pid")
_FILE_STATE = f"{_PID_FILE}.file"

# Sentinel pushed onto the queue to stop the worker after the current upload.
STOP = None

# How often the reconcile loop sweeps for stranded recordings.
RECONCILE_INTERVAL = 5  # seconds

# &&&& new (scaffold)
# How often the event poller pulls the lesson schedule.
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "300"))  # seconds


def active_recording_file() -> str | None:
    """Realpath of the newest segment record.sh is currently writing, if any.

    FILE_STATE holds the session prefix (recordings/session_<ts>_); ffmpeg writes
    segments sequentially, so the highest-numbered one is the active file and
    everything below it is finished. Returns None when nothing is recording.
    """
    try:
        with open(_FILE_STATE) as fh:
            prefix = fh.read().strip()
    except FileNotFoundError:
        return None
    if not prefix:
        return None
    segments = glob.glob(f"{prefix}*.mp4")
    if not segments:
        return None
    newest = max(segments, key=lambda p: segment_part(p) or -1)
    return os.path.realpath(newest)


def process_segment(conn, ids, path: str, active: str | None, queue: asyncio.Queue):
    """Reconcile one changed file against the DB; enqueue it if finished.

    The active (newest) segment gets a 'recording' row created if missing but is
    never enqueued — it's still being written. Any other segment is finished:
    ensure a row exists, and if it hasn't already moved past 'in_queue', flip it
    and hand it to the worker. Sync and side-effect-contained so tests can drive
    it directly.
    """
    if not path.endswith(".mp4"):
        return
    part = segment_part(path)
    if part is None:
        return  # not a segment we manage (stray file)

    if active is not None and os.path.realpath(path) == active:
        create_video_row(conn, ids, path, part)  # idempotent
        return

    row = find_video_by_path(conn, path)
    if row is None:
        video_id = create_video_row(conn, ids, path, part)
        status_id = ids["recording"]
    else:
        video_id, status_id = row["id"], row["status_mapping_id"]
    if status_id not in (ids["recording"], ids["in_queue"]):
        return  # already uploading / uploaded / failed
    set_status(conn, video_id, ids["in_queue"])
    queue.put_nowait((video_id, path))
    log.info("queued video id=%s part=%s %s", video_id, part, path)


async def watch_recordings(conn, ids, queue: asyncio.Queue, stop: asyncio.Event):
    """Watch the recordings dir; enqueue finished segments."""
    from watchfiles import awatch

    os.makedirs(RECORDINGS_DIR, exist_ok=True)
    log.info("watching %s for finished segments", RECORDINGS_DIR)

    async for changes in awatch(RECORDINGS_DIR, stop_event=stop):
        active = active_recording_file()
        for _change, path in changes:
            process_segment(conn, ids, path, active, queue)

    log.info("watch_recordings stopped")


async def reconcile_stranded(conn, ids, queue: asyncio.Queue, stop: asyncio.Event):
    """Safety net for watch_recordings: re-queue finished recordings it missed.

    The watcher skips a file while record.sh still flags it active, and a recording's
    final write usually lands inside that window — so on stop the row can sit at
    'recording' with no further filesystem event to wake the watcher. This runs the
    same reconciliation as startup, on an interval, so any stranded recording is
    picked up within RECONCILE_INTERVAL seconds. recover_stranded_recordings skips
    the file that is currently being written, so an in-progress recording is safe.
    """
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=RECONCILE_INTERVAL)
        except asyncio.TimeoutError:
            pass  # interval elapsed — time to sweep
        if stop.is_set():
            break
        for row in recover_stranded_recordings(conn, ids, active_recording_file()):
            queue.put_nowait((row["id"], row["file_path"]))
            log.info("reconciled stranded recording id=%s -> in_queue", row["id"])

    log.info("reconcile loop stopped")


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


# &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&
# new chunk — scaffold, remove on implementation
# &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&
# --- Event fetching & scheduling ---------------------------------------------
#
# ServerEvent — one row of fetch_events.sh JSON (see db.py for the full shape):
#   {"remote_id", "type" ("workshop"|"cohort"), "name", "title", "start_time", "end_time"}
#   name = group key (-> *_mapping); title = per-occurrence label (-> event.title)
#
# STUBS (Plan 1): the coroutines run (so the daemon works end-to-end on fake data)
# but the real fetch/sync/scheduling logic lands in Plan 2. `# should …` = tests.


async def _fetch_events() -> list[dict]:
    """Compute today's 09:00–21:00 London window, call fetch_events.sh, parse JSON.

    SEAM: fetch_events.sh sources .env + curls; the window is computed TZ-aware
    (Europe/London) then converted to the server's UTC. Mirrors upload_worker's
    create_subprocess_exec pattern.
    """
    # should return [] on non-zero exit or unparseable output
    return [  # fake walking-skeleton data (Plan 2 replaces with the real fetch)
        {
            "remote_id": "fake:workshop:1",
            "type": "workshop",
            "name": "Fake Workshop",  # workshops: name == title (event IS the occurrence)
            "title": "Fake Workshop",
            "start_time": "2026-06-30T13:00:00Z",
            "end_time": "2026-06-30T15:00:00Z",
        },
        {
            "remote_id": "fake:cohort:1",
            "type": "cohort",
            "name": "FAC30",  # cohort group key -> get_or_create_cohort (dedupes)
            "title": "Week 3 - Fake Lesson",  # this occurrence -> event.title
            "start_time": "2026-06-30T10:00:00Z",
            "end_time": "2026-06-30T17:00:00Z",
        },
    ]


async def poll_events(conn, ids, replan: asyncio.Event, stop: asyncio.Event):
    """Periodically pull the lesson schedule into the DB; wake the scheduler after.

    Polls immediately on startup (fresh schedule at boot) then every POLL_INTERVAL,
    cancellable by `stop` via the reconcile_stranded wait_for pattern.
    """
    log.info("event poller started (every %ss)", POLL_INTERVAL)
    while not stop.is_set():
        # should each tick: _fetch_events() -> sync_events() -> replan.set()
        # should swallow+log a failed poll (next tick retries) — never crash the loop
        try:
            events = await _fetch_events()
            synced = sync_events(conn, events)
            log.info("polled %d event(s) -> synced %d", len(events), synced)
            replan.set()
        except Exception:  # noqa: BLE001 — a poll failure must not kill the loop
            log.exception("event poll failed; retrying next tick")
        try:
            await asyncio.wait_for(stop.wait(), timeout=POLL_INTERVAL)
        except asyncio.TimeoutError:
            pass  # interval elapsed — poll again
    log.info("event poller stopped")


async def scheduler(conn, ids, replan: asyncio.Event, stop: asyncio.Event):
    """Plan recordings from the event table: start at start_time, stop at end_time.

    STEP-4 shared filming mechanism (same for workshop & future cohort events).
    Plan 1 just proves the wake wiring; the planning logic lands in Plan 2.
    """
    log.info("scheduler started")
    while not stop.is_set():
        # should, on entry & each wake: active_event(now) and not recording -> start (resume)
        # should otherwise sleep until next_event(now).start_time OR until replan fires
        # should, on start: snapshot end_time -> record.sh start --scheduled --end-time <iso>
        # should stop at the snapshot; ignore later poll changes to an in-progress recording
        # should skip (and log) a new event overlapping one already recording
        # should guard via record.sh status before start/stop (no double start/stop)
        replan.clear()
        waiters = {
            asyncio.create_task(stop.wait()),
            asyncio.create_task(replan.wait()),
        }
        _done, pending = await asyncio.wait(
            waiters, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        if stop.is_set():
            break
        log.info("scheduler re-planning (woken by poll)")
    log.info("scheduler stopped")


# &&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&

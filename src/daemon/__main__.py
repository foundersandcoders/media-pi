"""Daemon entry point.

Currently runs a single coroutine pair (the upload pipeline). The scheduler and
MQTT listener will slot in here later as additional tasks. Managed by systemd on
the Pi (see deploy/media-pi-daemon.service); run directly with `python -m daemon`
for local development.
"""

import asyncio
import logging
import signal

from .db import (
    get_connection,
    load_status_ids,
    pending_videos,
    recover_in_flight,
    recover_stranded_recordings,
)
from .pipeline import (
    STOP,
    active_recording_file,
    # &&&& new (scaffold)
    poll_events,
    reconcile_stranded,
    # &&&& new (scaffold)
    scheduler,
    upload_worker,
    watch_recordings,
)
from .process import clear_pid, write_pid

log = logging.getLogger("daemon")

_REQUIRED_STATUSES = {"recording", "in_queue", "uploading", "uploaded", "failed"}


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # watchfiles logs an INFO line per change batch — far too chatty for the journal.
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
    write_pid()
    conn = get_connection()
    try:
        status_ids = load_status_ids(conn)
        missing = _REQUIRED_STATUSES - status_ids.keys()
        if missing:
            raise SystemExit(
                f"status_mapping missing {sorted(missing)} — run `make db-init` first"
            )

        reset = recover_in_flight(conn, status_ids)
        if reset:
            log.info("recovered %d interrupted upload(s) -> in_queue", reset)

        stranded = recover_stranded_recordings(
            conn, status_ids, active_recording_file()
        )
        if stranded:
            log.info("recovered %d stranded segment(s) -> in_queue", len(stranded))

        queue: asyncio.Queue = asyncio.Queue()
        for row in pending_videos(conn, status_ids):
            queue.put_nowait((row["id"], row["file_path"]))
        log.info("enqueued %d pending upload(s)", queue.qsize())

        stop = asyncio.Event()
        # !!!! edit (scaffold)
        # replan: poll_events sets it after each sync; scheduler awaits it to re-plan.
        replan = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)

        watch_task = asyncio.create_task(
            watch_recordings(conn, status_ids, queue, stop)
        )
        worker_task = asyncio.create_task(upload_worker(conn, status_ids, queue))
        reconcile_task = asyncio.create_task(
            reconcile_stranded(conn, status_ids, queue, stop)
        )
        # !!!! edit (scaffold)
        poll_task = asyncio.create_task(poll_events(conn, status_ids, replan, stop))
        sched_task = asyncio.create_task(scheduler(conn, status_ids, replan, stop))

        await stop.wait()
        log.info("shutdown signal received — draining")
        await watch_task  # awatch exits on the stop event
        await reconcile_task  # exits on the stop event
        # !!!! edit (scaffold)
        await poll_task  # exits on the stop event
        await sched_task  # exits on the stop event
        await queue.put(STOP)  # wake the worker once the in-flight upload finishes
        await worker_task
        log.info("daemon stopped cleanly")
    finally:
        conn.close()
        clear_pid()


def main_sync() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()

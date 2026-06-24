"""Daemon liveness via a PID file.

The daemon writes its PID on startup and removes it on clean exit. The TUI reads
the same file (default path, no env override needed) to report whether the daemon
is running — the two stay separate processes, this is just the signal between them.

Mirrors the PID-file pattern in src/core/record.sh: existence of the file plus a
live process owning the PID. A SIGKILL leaves a stale file; `running_pid` treats a
PID with no live process as not-running.
"""

import os

DAEMON_PID_FILE = os.environ.get("DAEMON_PID_FILE", "/tmp/fac-daemon.pid")


def write_pid() -> None:
    """Record this process as the running daemon."""
    with open(DAEMON_PID_FILE, "w") as fh:
        fh.write(str(os.getpid()))


def clear_pid() -> None:
    """Remove the PID file on clean shutdown. No-op if already gone."""
    try:
        os.remove(DAEMON_PID_FILE)
    except FileNotFoundError:
        pass


def running_pid() -> int | None:
    """Return the daemon's PID if a live process owns the PID file, else None.

    Handles a missing file, garbage contents, and a stale PID (process gone).
    """
    try:
        with open(DAEMON_PID_FILE) as fh:
            pid = int(fh.read().strip())
    except (FileNotFoundError, ValueError):
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None  # stale PID file — process is gone
    except PermissionError:
        return pid  # exists but owned by another user — still running
    return pid

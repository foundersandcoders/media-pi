import sqlite3
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCHEMA = Path(__file__).parent.parent / "core" / "schema.sql"
_DATA_DIR = _REPO_ROOT / "data"

# Sentinel the writers (daemon, record_start, TUI retry) touch on every DB commit;
# the TUI watches it with watchfiles and reloads its data widgets. This is how a
# separate writer process nudges the reader — SQLite has no cross-process change
# notification.
SENTINEL_FILE = _DATA_DIR / ".ui-dirty"


def notify_change() -> None:
    """Touch the UI sentinel so the TUI's watcher refreshes. Best-effort — a
    sentinel failure must never break a DB write."""
    try:
        _DATA_DIR.mkdir(exist_ok=True)
        SENTINEL_FILE.touch()
    except OSError:
        pass


def _current_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=_REPO_ROOT,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def get_db_path() -> Path:
    _DATA_DIR.mkdir(exist_ok=True)
    name = "media_pi.db" if _current_branch() == "main" else "media_pi_test.db"
    return _DATA_DIR / name


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL lets the daemon (writer) and the TUI (reader + retry writer) — separate
    # processes on the same file — operate concurrently. Persists on the DB file.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA.read_text())

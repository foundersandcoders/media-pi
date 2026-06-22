import sqlite3
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCHEMA = Path(__file__).parent.parent / "core" / "schema.sql"
_DATA_DIR = _REPO_ROOT / "data"


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
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA.read_text())

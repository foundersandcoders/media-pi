#!/usr/bin/env python3
"""Seeds required constant data. Safe to run on any DB, including live."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tui.db import get_connection, get_db_path, init_schema

# Tied to exit codes defined in src/core/record.sh and src/core/upload.sh.
ERROR_MAPPING = [
    {"exit_code": 1, "error_id": 1, "message": "Already recording"},
    {"exit_code": 2, "error_id": 1, "message": ".env not found"},
    {"exit_code": 2, "error_id": 2, "message": "File missing or empty"},
    {"exit_code": 2, "error_id": 3, "message": "File still being written by recorder"},
    {"exit_code": 3, "error_id": 1, "message": "Disk space below minimum threshold"},
    {"exit_code": 4, "error_id": 1, "message": "ffmpeg exited immediately — check log"},
    {"exit_code": 4, "error_id": 2, "message": "Register failed — API unreachable"},
    {"exit_code": 4, "error_id": 3, "message": "Register failed — auth rejected"},
    {
        "exit_code": 5,
        "error_id": 1,
        "message": "Confirm failed — video_url still NULL on server",
    },
]

# Upload/recording lifecycle states. Order is the natural progression; ids are
# assigned by insertion order but always looked up by name, never hardcoded.
STATUS_MAPPING = ["recording", "in_queue", "uploading", "uploaded", "failed"]


if __name__ == "__main__":
    db_path = get_db_path()
    print(f"Seeding constants → {db_path}")
    with get_connection() as conn:
        init_schema(conn)
        for name in STATUS_MAPPING:
            conn.execute(
                "INSERT OR IGNORE INTO status_mapping (name) VALUES (?)",
                (name,),
            )
        for e in ERROR_MAPPING:
            conn.execute(
                "INSERT OR IGNORE INTO error_mapping (exit_code, error_id, message)"
                " VALUES (:exit_code, :error_id, :message)",
                e,
            )
    print("Done.")

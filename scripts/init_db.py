#!/usr/bin/env python3
"""Creates the database and applies the schema. Safe to run repeatedly."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tui.db import get_connection, get_db_path, init_schema

if __name__ == "__main__":
    db_path = get_db_path()
    print(f"Initialising {db_path}")
    with get_connection() as conn:
        init_schema(conn)
    print("Done.")

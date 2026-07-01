-- Run via scripts/init_db.py. All statements are idempotent.
-- Connection must have PRAGMA foreign_keys = ON.

-- SCHEMA CHANGE: cohort identity only (id + name), mirroring workshop_mapping.
-- Populated by get_or_create_cohort during event polling (add-if-absent, keyed on
-- name e.g. "FACM9"). The old schedule-template columns (start_date/end_date/
-- session_*_time) are gone: events now come from polling, not a recurring generator,
-- and the per-lesson label ("Week 7 - …") arrives as event.title from the server, so
-- the Pi no longer computes week numbers.
CREATE TABLE IF NOT EXISTS cohort_mapping (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workshop_mapping (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS error_mapping (
    id         INTEGER PRIMARY KEY,
    exit_code  INTEGER NOT NULL,
    error_id   INTEGER NOT NULL,
    message    TEXT    NOT NULL,
    UNIQUE (exit_code, error_id)
);

-- Upload/recording lifecycle states. Seeded by scripts/seed_constants.py.
-- Normalised into a table (rather than a CHECK constraint) so new states are a
-- one-row INSERT instead of a table rebuild — SQLite can't ALTER a CHECK.
CREATE TABLE IF NOT EXISTS status_mapping (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS video (
    id                  INTEGER PRIMARY KEY,
    file_path           TEXT    NOT NULL,
    cohort_mapping_id   INTEGER REFERENCES cohort_mapping (id),
    workshop_mapping_id INTEGER REFERENCES workshop_mapping (id),
    recorded_at         TEXT    NOT NULL,
    video_size          INTEGER,
    video_length        INTEGER,
    status_mapping_id   INTEGER NOT NULL REFERENCES status_mapping (id),
    part                INTEGER NOT NULL DEFAULT 1,
    error_mapping_id    INTEGER REFERENCES error_mapping (id),
    CHECK (
        (cohort_mapping_id IS NOT NULL AND workshop_mapping_id IS NULL) OR
        (cohort_mapping_id IS NULL     AND workshop_mapping_id IS NOT NULL)
    )
);

-- SCHEMA CHANGE: remote_id is the server's globally-unique event id and our
-- upsert/dedup key. Set for every polled event — cohort AND workshop. UNIQUE
-- permits multiple NULLs in SQLite, so any manually-added event (no server id)
-- is unaffected by the dedup.
-- NOTE: CREATE TABLE IF NOT EXISTS won't add the column to an existing DB — this
-- branch recreates the test DB; production needs an ALTER TABLE migration. (SEAM)
CREATE TABLE IF NOT EXISTS event (
    id                  INTEGER PRIMARY KEY,
    -- !!!! edit (scaffold)
    remote_id           TEXT UNIQUE,        -- server id e.g. "attendance:42"; NULL only for manually-added events
    title               TEXT,               -- per-occurrence label from server e.g. "Week 7 - RAG"; display only, NULL for manual
    cohort_mapping_id   INTEGER REFERENCES cohort_mapping (id),
    workshop_mapping_id INTEGER REFERENCES workshop_mapping (id),
    start_time          TEXT NOT NULL,      -- ISO datetime
    end_time            TEXT NOT NULL,      -- ISO datetime
    CHECK (
        (cohort_mapping_id IS NOT NULL AND workshop_mapping_id IS NULL) OR
        (cohort_mapping_id IS NULL     AND workshop_mapping_id IS NOT NULL)
    )
);

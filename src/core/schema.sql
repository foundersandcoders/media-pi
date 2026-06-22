-- Run via scripts/init_db.py. All statements are idempotent.
-- Connection must have PRAGMA foreign_keys = ON.

CREATE TABLE IF NOT EXISTS cohort_mapping (
    id                  INTEGER PRIMARY KEY,
    name                TEXT    NOT NULL,
    start_date          TEXT    NOT NULL,
    end_date            TEXT    NOT NULL,
    session_start_time  TEXT    NOT NULL,
    session_end_time    TEXT    NOT NULL
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

CREATE TABLE IF NOT EXISTS video (
    id                  INTEGER PRIMARY KEY,
    file_path           TEXT    NOT NULL,
    cohort_mapping_id   INTEGER REFERENCES cohort_mapping (id),
    workshop_mapping_id INTEGER REFERENCES workshop_mapping (id),
    recorded_at         TEXT    NOT NULL,
    video_size          INTEGER,
    video_length        INTEGER,
    status              TEXT    NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'uploaded', 'failed')),
    part                INTEGER NOT NULL DEFAULT 1,
    error_mapping_id    INTEGER REFERENCES error_mapping (id),
    CHECK (
        (cohort_mapping_id IS NOT NULL AND workshop_mapping_id IS NULL) OR
        (cohort_mapping_id IS NULL     AND workshop_mapping_id IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS event (
    id                  INTEGER PRIMARY KEY,
    cohort_mapping_id   INTEGER REFERENCES cohort_mapping (id),
    workshop_mapping_id INTEGER REFERENCES workshop_mapping (id),
    start_time          TEXT NOT NULL,      -- ISO datetime
    end_time            TEXT NOT NULL,      -- ISO datetime
    CHECK (
        (cohort_mapping_id IS NOT NULL AND workshop_mapping_id IS NULL) OR
        (cohort_mapping_id IS NULL     AND workshop_mapping_id IS NOT NULL)
    )
);

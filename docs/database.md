# Database Design

## Purpose

The database serves two distinct functions:

1. **Upload history** — recording file metadata, upload status, and errors so the TUI can display and interact with past recordings and failed uploads.
2. **Scheduling** — storing upcoming events so the camera knows when it is going to film.

## Design principles

The schema follows 3NF. Cohorts and workshops are stored once as name-keyed mapping rows and referenced everywhere. Both are populated the same way — get-or-created by name as the schedule is polled from the server. Every occurrence (a cohort lesson or an open workshop) is its own `event` row carrying its own label (`title`) and times, so nothing is derived from a recurring cadence.

## Tables

### `cohort_mapping`

Cohort identity only — one row per cohort, mirroring `workshop_mapping`. Rows are get-or-created by name as events are polled (add if absent). Session dates and times are no longer stored here: every session arrives as its own `event`, and the per-lesson label comes down as `event.title`.

| Column | Type | Notes |
|---|---|---|
| id | PK | |
| name | text | Cohort group key, e.g. "FACM9" |

---

### `workshop_mapping`

Workshops are repeated across cohorts and open sessions, so the name is stored once here. There is no time on this table because open workshops do not happen at a regular time — time belongs on the event.

| Column | Type | Notes |
|---|---|---|
| id | PK | |
| name | text | |

---

### `error_mapping`

Provides reliable, database-driven error messages for the failed uploads panel. The `exit_code` and `error_id` together are always unique — multiple rows can share an exit code but the combination is distinct, allowing more specific messages per failure mode.

| Column | Type | Notes |
|---|---|---|
| id | PK | |
| exit_code | integer | |
| error_id | integer | |
| message | text | Human-readable message shown in TUI |

**Constraint:** `UNIQUE(exit_code, error_id)`

---

### `video`

A single recording session writes to multiple files. Each file is one row, with a `part` field to indicate position within that session.

A video belongs to either a cohort session or a workshop — never both, never neither. The human-readable name shown in upload history is derived from whichever FK is set: for a cohort video the label is currently the recording date (the per-lesson `event.title` isn't linked to videos yet); for a workshop video, it is the workshop name.

| Column | Type | Notes |
|---|---|---|
| id | PK | |
| file_path | text | Path written by ffmpeg |
| cohort_mapping_id | FK → cohort_mapping | Nullable |
| workshop_mapping_id | FK → workshop_mapping | Nullable |
| recorded_at | timestamp | Start time of this part |
| video_size | integer | Bytes |
| video_length | integer | Seconds |
| status | enum | `pending`, `uploaded`, `failed` |
| part | integer | Part number within the session |
| error_mapping_id | FK → error_mapping | Nullable; set on failure |

**Constraint:** exactly one of `cohort_mapping_id` / `workshop_mapping_id` must be non-null.

---

### `event`

Stores the polled schedule — what the camera should film and when. The daemon polls the FAC server (`fetch_events.sh` → `sync_events`) and upserts one row per occurrence, keyed on `remote_id`. Both cohort lessons and open workshops flow through the same path; `title` holds the server's per-occurrence label. Events are no longer prefilled from a cohort cadence.

| Column | Type | Notes |
|---|---|---|
| id | PK | |
| remote_id | text | Server's globally-unique id and upsert key; UNIQUE, NULL only for manually-added events |
| title | text | Per-occurrence label from the server, e.g. "Week 7 - RAG"; display only |
| cohort_mapping_id | FK → cohort_mapping | Nullable |
| workshop_mapping_id | FK → workshop_mapping | Nullable |
| start_time | timestamp | ISO datetime |
| end_time | timestamp | ISO datetime |

**Constraint:** exactly one of `cohort_mapping_id` / `workshop_mapping_id` must be non-null.

---

## Patterns

- **Mutual exclusivity** — both `video` and `event` carry two nullable FKs (cohort / workshop) with a check constraint enforcing exactly one is set. This is what lets a single query over either table produce a human-readable name regardless of type.
- **Mapping tables** — cohorts and workshops are defined once and referenced everywhere, keeping names consistent and queryable.
- **Status over bool** — `video.status` is an enum rather than an `is_uploaded` boolean so that failed uploads are a first-class state that can be surfaced in the TUI.

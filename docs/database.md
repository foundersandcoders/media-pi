# Database Design

## Purpose

The database serves two distinct functions:

1. **Upload history** — recording file metadata, upload status, and errors so the TUI can display and interact with past recordings and failed uploads.
2. **Scheduling** — storing upcoming events so the camera knows when it is going to film.

## Design principles

The schema follows 3NF. This is achievable because FAC has a predictable structure: regular cohorts with known names, start and end dates, and a fixed weekly session time. Workshops are reusable where the same workshop runs multiple times, so the name is stored once and referenced.

## Tables

### `cohort_mapping`

Stores each cohort as a single row. Because cohorts meet at a fixed time every week, the session start and end time are static properties of the cohort itself rather than repeated on every event.

| Column | Type | Notes |
|---|---|---|
| id | PK | |
| name | text | |
| start_date | date | Used to calculate week numbers and to prefill events |
| end_date | date | Upper boundary for event prefill |
| session_start_time | time | Weekly recurring start time |
| session_end_time | time | Weekly recurring end time |

Week number is derived at query time: `(today - start_date) / 7`.

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

A video belongs to either a cohort session or a workshop — never both, never neither. The human-readable name shown in upload history is derived from whichever FK is set: for a cohort video, the name is the week number (calculated from cohort `start_date`); for a workshop video, it is the workshop name.

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

Stores scheduled recordings. Cohort events are prefilled for the full cohort duration (using `cohort_mapping.start_date` and `end_date`) — since we know all the session dates in advance. Open workshop events are added individually and must have explicit start and end times, since there is no regular cadence to derive them from.

| Column | Type | Notes |
|---|---|---|
| id | PK | |
| cohort_mapping_id | FK → cohort_mapping | Nullable |
| workshop_mapping_id | FK → workshop_mapping | Nullable |
| start_time | timestamp | Required for workshop events |
| end_time | timestamp | Required for workshop events |

**Constraint:** exactly one of `cohort_mapping_id` / `workshop_mapping_id` must be non-null.

---

## Patterns

- **Mutual exclusivity** — both `video` and `event` carry two nullable FKs (cohort / workshop) with a check constraint enforcing exactly one is set. This is what lets a single query over either table produce a human-readable name regardless of type.
- **Mapping tables** — cohorts and workshops are defined once and referenced everywhere, keeping names consistent and queryable.
- **Status over bool** — `video.status` is an enum rather than an `is_uploaded` boolean so that failed uploads are a first-class state that can be surfaced in the TUI.

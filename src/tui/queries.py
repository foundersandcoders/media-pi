from .db import get_connection


def get_all_videos():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                COALESCE(c.name, 'Open Workshop') AS cohort,
                CASE
                    WHEN c.id IS NOT NULL
                    -- cohort session: the per-lesson label now lives on event.title,
                    -- which video rows don't link to yet — show the date for now.
                    THEN date(v.recorded_at)
                    ELSE w.name
                END AS name,
                v.part,
                v.video_size,
                v.recorded_at,
                s.name AS status
            FROM video v
            LEFT JOIN cohort_mapping c ON v.cohort_mapping_id = c.id
            LEFT JOIN workshop_mapping w ON v.workshop_mapping_id = w.id
            LEFT JOIN status_mapping s ON v.status_mapping_id = s.id
            ORDER BY v.recorded_at DESC
        """
        ).fetchall()


def get_failed_videos():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                v.id,
                COALESCE(c.name, 'Open Workshop') AS cohort,
                CASE
                    WHEN c.id IS NOT NULL
                    -- cohort session: the per-lesson label now lives on event.title,
                    -- which video rows don't link to yet — show the date for now.
                    THEN date(v.recorded_at)
                    ELSE w.name
                END AS name,
                v.part,
                v.video_size,
                v.recorded_at,
                s.name AS status,
                v.file_path,
                e.message AS error_message
            FROM video v
            LEFT JOIN cohort_mapping c ON v.cohort_mapping_id = c.id
            LEFT JOIN workshop_mapping w ON v.workshop_mapping_id = w.id
            LEFT JOIN status_mapping s ON v.status_mapping_id = s.id
            LEFT JOIN error_mapping e ON v.error_mapping_id = e.id
            WHERE s.name = 'failed'
            ORDER BY v.recorded_at DESC
        """
        ).fetchall()

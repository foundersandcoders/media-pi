from .db import get_connection


def get_all_videos():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                COALESCE(c.name, 'Open Workshop') AS cohort,
                CASE
                    WHEN c.id IS NOT NULL
                    THEN 'Week ' || CAST(
                        (julianday(date(v.recorded_at)) - julianday(c.start_date)) / 7 + 1
                        AS INTEGER)
                    ELSE w.name
                END AS name,
                v.part,
                v.video_size,
                v.recorded_at,
                v.status
            FROM video v
            LEFT JOIN cohort_mapping c ON v.cohort_mapping_id = c.id
            LEFT JOIN workshop_mapping w ON v.workshop_mapping_id = w.id
            ORDER BY v.recorded_at DESC
        """
        ).fetchall()


def get_failed_videos():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                COALESCE(c.name, 'Open Workshop') AS cohort,
                CASE
                    WHEN c.id IS NOT NULL
                    THEN 'Week ' || CAST(
                        (julianday(date(v.recorded_at)) - julianday(c.start_date)) / 7 + 1
                        AS INTEGER)
                    ELSE w.name
                END AS name,
                v.part,
                v.video_size,
                v.recorded_at,
                v.status,
                v.file_path,
                e.message AS error_message
            FROM video v
            LEFT JOIN cohort_mapping c ON v.cohort_mapping_id = c.id
            LEFT JOIN workshop_mapping w ON v.workshop_mapping_id = w.id
            LEFT JOIN error_mapping e ON v.error_mapping_id = e.id
            WHERE v.status = 'failed'
            ORDER BY v.recorded_at DESC
        """
        ).fetchall()

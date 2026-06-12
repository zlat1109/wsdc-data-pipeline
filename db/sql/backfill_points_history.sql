-- Build SCD2 history from staging.changed_dancers_points_info (backfill).
-- Each row is a snapshot at update_date; we keep only rows where total_points changed.
-- Caller must TRUNCATE history.dancer_points_history before running (first backfill only).

WITH normalized AS (
    SELECT
        s.dancer_id::int AS dancer_id,
        CASE LOWER(TRIM(s.role))
            WHEN 'leader' THEN 'Leader'
            WHEN 'follower' THEN 'Follower'
        END AS role,
        TRIM(s.dance) AS dance,
        COALESCE(l.level, TRIM(s.level)) AS level,
        COALESCE(NULLIF(TRIM(s.total_points), '')::int, 0) AS total_points,
        NULLIF(TRIM(s.update_date), '')::date AS snap_date
    FROM staging.changed_dancers_points_info s
    LEFT JOIN core.levels l
        ON UPPER(TRIM(s.level)) = l.level_abbr OR TRIM(s.level) = l.level
    WHERE s.dancer_id ~ '^\d+$'
      AND NULLIF(TRIM(s.update_date), '') IS NOT NULL
      AND COALESCE(l.level, TRIM(s.level)) IN (SELECT level FROM core.levels)
),
deduped AS (
    SELECT DISTINCT ON (dancer_id, role, dance, level, snap_date)
        dancer_id, role, dance, level, total_points, snap_date
    FROM normalized
    ORDER BY dancer_id, role, dance, level, snap_date, total_points
),
with_prev AS (
    SELECT
        *,
        LAG(total_points) OVER (
            PARTITION BY dancer_id, role, dance, level
            ORDER BY snap_date
        ) AS prev_points
    FROM deduped
),
changes AS (
    SELECT dancer_id, role, dance, level, total_points, snap_date
    FROM with_prev
    WHERE prev_points IS NULL OR prev_points <> total_points
),
intervals AS (
    SELECT
        dancer_id,
        role,
        dance,
        level,
        total_points,
        snap_date AS valid_from,
        LEAD(snap_date) OVER (
            PARTITION BY dancer_id, role, dance, level
            ORDER BY snap_date
        ) AS next_from
    FROM changes
)
INSERT INTO history.dancer_points_history (
    dancer_id, role, dance, level, total_points, valid_from, valid_to, run_id
)
SELECT
    dancer_id,
    role,
    dance,
    level,
    total_points,
    valid_from,
    CASE WHEN next_from IS NOT NULL THEN next_from - INTERVAL '1 day' END::date,
    %(run_id)s
FROM intervals;

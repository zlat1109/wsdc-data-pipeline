-- Record points changes (staging vs current core) before full core refresh.
-- Closes open history intervals and inserts new versions.

WITH staging_norm AS (
    SELECT
        s.dancer_id::int AS dancer_id,
        CASE LOWER(TRIM(s.role))
            WHEN 'leader' THEN 'Leader'
            WHEN 'follower' THEN 'Follower'
        END AS role,
        TRIM(s.dance) AS dance,
        COALESCE(l.level, TRIM(s.level)) AS level,
        COALESCE(NULLIF(TRIM(s.total_points), '')::int, 0) AS total_points,
        COALESCE(NULLIF(TRIM(s.update_date), '')::date, CURRENT_DATE) AS change_date
    FROM staging.dancers_points_info s
    LEFT JOIN core.levels l
        ON UPPER(TRIM(s.level)) = l.level_abbr OR TRIM(s.level) = l.level
    WHERE s.dancer_id ~ '^\d+$'
      AND COALESCE(l.level, TRIM(s.level)) IN (SELECT level FROM core.levels)
),
changed AS (
    SELECT sn.*
    FROM staging_norm sn
    LEFT JOIN core.dancer_points c
        ON c.dancer_id = sn.dancer_id
       AND c.role = sn.role
       AND c.dance = sn.dance
       AND c.level = sn.level
    WHERE c.dancer_id IS NULL OR c.total_points IS DISTINCT FROM sn.total_points
),
close_old AS (
    UPDATE history.dancer_points_history h
    SET valid_to = c.change_date - INTERVAL '1 day'
    FROM changed c
    WHERE h.dancer_id = c.dancer_id
      AND h.role = c.role
      AND h.dance = c.dance
      AND h.level = c.level
      AND h.valid_to IS NULL
    RETURNING h.dancer_id
)
INSERT INTO history.dancer_points_history (
    dancer_id, role, dance, level, total_points, valid_from, valid_to, run_id
)
SELECT
    dancer_id, role, dance, level, total_points, change_date, NULL, %(run_id)s
FROM changed;

-- Record points changes (staging vs current core) before full core refresh.
-- Closes open history intervals and inserts new versions.
--
-- Same-day re-entry: PK is (dancer_id, role, dance, level, valid_from). Closing an
-- open interval that already starts on change_date and inserting again collides.
-- Handle that by updating the open row in place; only close older opens.

WITH staging_norm AS (
    SELECT DISTINCT ON (dancer_id, role, dance, level)
        dancer_id,
        role,
        dance,
        level,
        total_points,
        change_date
    FROM (
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
          AND CASE LOWER(TRIM(s.role))
                WHEN 'leader' THEN 'Leader'
                WHEN 'follower' THEN 'Follower'
              END IS NOT NULL
    ) raw
    ORDER BY dancer_id, role, dance, level, change_date DESC, total_points DESC
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
-- Same calendar day as an existing open interval: overwrite points, keep valid_from.
upd_same_day AS (
    UPDATE history.dancer_points_history h
    SET total_points = c.total_points,
        run_id = %(run_id)s
    FROM changed c
    WHERE h.dancer_id = c.dancer_id
      AND h.role = c.role
      AND h.dance = c.dance
      AND h.level = c.level
      AND h.valid_to IS NULL
      AND h.valid_from = c.change_date
    RETURNING h.dancer_id, h.role, h.dance, h.level
),
-- Older open intervals only (same-day opens are handled by upd_same_day).
close_old AS (
    UPDATE history.dancer_points_history h
    SET valid_to = c.change_date - INTERVAL '1 day'
    FROM changed c
    WHERE h.dancer_id = c.dancer_id
      AND h.role = c.role
      AND h.dance = c.dance
      AND h.level = c.level
      AND h.valid_to IS NULL
      AND h.valid_from < c.change_date
    RETURNING h.dancer_id
)
INSERT INTO history.dancer_points_history (
    dancer_id, role, dance, level, total_points, valid_from, valid_to, run_id
)
SELECT
    c.dancer_id, c.role, c.dance, c.level, c.total_points, c.change_date, NULL, %(run_id)s
FROM changed c
WHERE NOT EXISTS (
    SELECT 1
    FROM upd_same_day u
    WHERE u.dancer_id = c.dancer_id
      AND u.role = c.role
      AND u.dance = c.dance
      AND u.level = c.level
)
ON CONFLICT (dancer_id, role, dance, level, valid_from) DO UPDATE
SET total_points = EXCLUDED.total_points,
    valid_to = NULL,
    run_id = EXCLUDED.run_id;

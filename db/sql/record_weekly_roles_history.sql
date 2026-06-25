-- Record role-summary changes (staging vs current core) before full core refresh.
-- Closes open history intervals and inserts new versions. Identity: dancer_id.
-- Tracked attributes: the full dancer_roles row (compared via md5 signature).

WITH staging_norm AS (
    SELECT
        s.dancer_id::int AS dancer_id,
        NULLIF(TRIM(s.dancer_name), '') AS dancer_name,
        NULLIF(TRIM(s.dominate_role), '') AS dominate_role,
        COALESCE(l1.level, TRIM(s.dominate_required)) AS dominate_required,
        COALESCE(l2.level, TRIM(s.dominate_allowed)) AS dominate_allowed,
        NULLIF(TRIM(s.non_dominate_role), '') AS non_dominate_role,
        COALESCE(l3.level, TRIM(s.non_dominate_required)) AS non_dominate_required,
        COALESCE(l4.level, TRIM(s.non_dominate_allowed)) AS non_dominate_allowed,
        COALESCE(l5.level, TRIM(s.non_dominate_recommended)) AS non_dominate_recommended,
        NULLIF(TRIM(s.non_dominate_role_highest_level_points), '')
            AS non_dominate_role_highest_level_points,
        COALESCE(l6.level, TRIM(s.non_dominate_role_highest_level))
            AS non_dominate_role_highest_level,
        COALESCE(NULLIF(TRIM(s.update_date), '')::date, CURRENT_DATE) AS change_date
    FROM staging.dancer_role_info s
    LEFT JOIN core.levels l1
        ON UPPER(TRIM(s.dominate_required)) = l1.level_abbr OR TRIM(s.dominate_required) = l1.level
    LEFT JOIN core.levels l2
        ON UPPER(TRIM(s.dominate_allowed)) = l2.level_abbr OR TRIM(s.dominate_allowed) = l2.level
    LEFT JOIN core.levels l3
        ON UPPER(TRIM(s.non_dominate_required)) = l3.level_abbr OR TRIM(s.non_dominate_required) = l3.level
    LEFT JOIN core.levels l4
        ON UPPER(TRIM(s.non_dominate_allowed)) = l4.level_abbr OR TRIM(s.non_dominate_allowed) = l4.level
    LEFT JOIN core.levels l5
        ON UPPER(TRIM(s.non_dominate_recommended)) = l5.level_abbr OR TRIM(s.non_dominate_recommended) = l5.level
    LEFT JOIN core.levels l6
        ON UPPER(TRIM(s.non_dominate_role_highest_level)) = l6.level_abbr OR TRIM(s.non_dominate_role_highest_level) = l6.level
    WHERE s.dancer_id ~ '^\d+$'
),
staging_sig AS (
    SELECT
        *,
        md5(
            concat_ws('|',
                COALESCE(dancer_name, ''),
                COALESCE(dominate_role, ''),
                COALESCE(dominate_required, ''),
                COALESCE(dominate_allowed, ''),
                COALESCE(non_dominate_role, ''),
                COALESCE(non_dominate_required, ''),
                COALESCE(non_dominate_allowed, ''),
                COALESCE(non_dominate_recommended, ''),
                COALESCE(non_dominate_role_highest_level_points, ''),
                COALESCE(non_dominate_role_highest_level, '')
            )
        ) AS sig
    FROM staging_norm
),
current_full AS (
    -- dancer_name lives on core.dancers; fold it in for comparison
    SELECT
        c.dancer_id,
        md5(
            concat_ws('|',
                COALESCE(d.dancer_name, ''),
                COALESCE(c.dominate_role, ''),
                COALESCE(c.dominate_required, ''),
                COALESCE(c.dominate_allowed, ''),
                COALESCE(c.non_dominate_role, ''),
                COALESCE(c.non_dominate_required, ''),
                COALESCE(c.non_dominate_allowed, ''),
                COALESCE(c.non_dominate_recommended, ''),
                COALESCE(c.non_dominate_role_highest_level_points, ''),
                COALESCE(c.non_dominate_role_highest_level, '')
            )
        ) AS sig
    FROM core.dancer_roles c
    JOIN core.dancers d ON d.dancer_id = c.dancer_id
),
changed AS (
    SELECT sn.*
    FROM staging_sig sn
    LEFT JOIN current_full cf ON cf.dancer_id = sn.dancer_id
    WHERE cf.dancer_id IS NULL OR cf.sig IS DISTINCT FROM sn.sig
),
close_old AS (
    UPDATE history.dancer_roles_history h
    SET valid_to = c.change_date - INTERVAL '1 day'
    FROM changed c
    WHERE h.dancer_id = c.dancer_id
      AND h.valid_to IS NULL
    RETURNING h.dancer_id
)
INSERT INTO history.dancer_roles_history (
    dancer_id, dancer_name, dominate_role, dominate_required, dominate_allowed,
    non_dominate_role, non_dominate_required, non_dominate_allowed,
    non_dominate_recommended, non_dominate_role_highest_level_points,
    non_dominate_role_highest_level, valid_from, valid_to, run_id
)
SELECT
    dancer_id, dancer_name, dominate_role, dominate_required, dominate_allowed,
    non_dominate_role, non_dominate_required, non_dominate_allowed,
    non_dominate_recommended, non_dominate_role_highest_level_points,
    non_dominate_role_highest_level, change_date, NULL, %(run_id)s
FROM changed;

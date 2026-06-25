-- Build SCD2 role history from staging.changed_dancer_role_info (backfill).
-- Each CSV row is a snapshot at update_date; keep only rows where any tracked
-- attribute changed vs the previous snapshot for that dancer.
-- Caller must TRUNCATE history.dancer_roles_history before running (first backfill only).

WITH normalized AS (
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
        NULLIF(TRIM(s.update_date), '')::date AS snap_date
    FROM staging.changed_dancer_role_info s
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
      AND NULLIF(TRIM(s.update_date), '') IS NOT NULL
),
deduped AS (
    SELECT DISTINCT ON (dancer_id, snap_date)
        dancer_id, dancer_name, dominate_role, dominate_required, dominate_allowed,
        non_dominate_role, non_dominate_required, non_dominate_allowed,
        non_dominate_recommended, non_dominate_role_highest_level_points,
        non_dominate_role_highest_level, snap_date
    FROM normalized
    ORDER BY dancer_id, snap_date, dominate_required, dominate_allowed
),
signed AS (
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
    FROM deduped
),
with_prev AS (
    SELECT
        *,
        LAG(sig) OVER (PARTITION BY dancer_id ORDER BY snap_date) AS prev_sig
    FROM signed
),
changes AS (
    SELECT * FROM with_prev
    WHERE prev_sig IS NULL OR prev_sig <> sig
),
intervals AS (
    SELECT
        *,
        LEAD(snap_date) OVER (PARTITION BY dancer_id ORDER BY snap_date) AS next_from
    FROM changes
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
    non_dominate_role_highest_level,
    snap_date,
    CASE WHEN next_from IS NOT NULL THEN next_from - INTERVAL '1 day' END::date,
    %(run_id)s
FROM intervals;

-- Record role-summary changes (staging vs current core) before full core refresh.
-- Closes open history intervals and inserts new versions. Identity: dancer_id.
-- Tracked attributes: dominate/non-dominate divisions only (name -> dancer_names_history).
--
-- Same-day re-entry: PK is (dancer_id, valid_from). Closing an open interval that
-- already starts on change_date and inserting again collides. Update in place;
-- only close older opens.

WITH staging_norm AS (
    SELECT
        s.dancer_id::int AS dancer_id,
        COALESCE(
            NULLIF(TRIM(s.dancer_name), ''),
            d.dancer_name
        ) AS dancer_name,
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
    LEFT JOIN core.dancers d ON d.dancer_id = s.dancer_id::int
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
        core.dancer_roles_division_sig(
            dominate_role,
            dominate_required,
            dominate_allowed,
            non_dominate_role,
            non_dominate_required,
            non_dominate_allowed,
            non_dominate_recommended,
            non_dominate_role_highest_level_points,
            non_dominate_role_highest_level
        ) AS sig
    FROM staging_norm
),
current_full AS (
    SELECT
        c.dancer_id,
        core.dancer_roles_division_sig(
            c.dominate_role,
            c.dominate_required,
            c.dominate_allowed,
            c.non_dominate_role,
            c.non_dominate_required,
            c.non_dominate_allowed,
            c.non_dominate_recommended,
            c.non_dominate_role_highest_level_points,
            c.non_dominate_role_highest_level
        ) AS sig
    FROM core.dancer_roles c
),
changed AS (
    SELECT sn.*
    FROM staging_sig sn
    LEFT JOIN current_full cf ON cf.dancer_id = sn.dancer_id
    WHERE cf.dancer_id IS NULL OR cf.sig IS DISTINCT FROM sn.sig
),
-- Same calendar day as an existing open interval: overwrite attributes.
upd_same_day AS (
    UPDATE history.dancer_roles_history h
    SET dancer_name = c.dancer_name,
        dominate_role = c.dominate_role,
        dominate_required = c.dominate_required,
        dominate_allowed = c.dominate_allowed,
        non_dominate_role = c.non_dominate_role,
        non_dominate_required = c.non_dominate_required,
        non_dominate_allowed = c.non_dominate_allowed,
        non_dominate_recommended = c.non_dominate_recommended,
        non_dominate_role_highest_level_points = c.non_dominate_role_highest_level_points,
        non_dominate_role_highest_level = c.non_dominate_role_highest_level,
        run_id = %(run_id)s
    FROM changed c
    WHERE h.dancer_id = c.dancer_id
      AND h.valid_to IS NULL
      AND h.valid_from = c.change_date
    RETURNING h.dancer_id
),
-- Older open intervals only (same-day opens are handled by upd_same_day).
close_old AS (
    UPDATE history.dancer_roles_history h
    SET valid_to = c.change_date - INTERVAL '1 day'
    FROM changed c
    WHERE h.dancer_id = c.dancer_id
      AND h.valid_to IS NULL
      AND h.valid_from < c.change_date
    RETURNING h.dancer_id
)
INSERT INTO history.dancer_roles_history (
    dancer_id, dancer_name, dominate_role, dominate_required, dominate_allowed,
    non_dominate_role, non_dominate_required, non_dominate_allowed,
    non_dominate_recommended, non_dominate_role_highest_level_points,
    non_dominate_role_highest_level, valid_from, valid_to, run_id
)
SELECT
    c.dancer_id, c.dancer_name, c.dominate_role, c.dominate_required, c.dominate_allowed,
    c.non_dominate_role, c.non_dominate_required, c.non_dominate_allowed,
    c.non_dominate_recommended, c.non_dominate_role_highest_level_points,
    c.non_dominate_role_highest_level, c.change_date, NULL, %(run_id)s
FROM changed c
WHERE NOT EXISTS (
    SELECT 1 FROM upd_same_day u WHERE u.dancer_id = c.dancer_id
)
ON CONFLICT (dancer_id, valid_from) DO UPDATE
SET dancer_name = EXCLUDED.dancer_name,
    dominate_role = EXCLUDED.dominate_role,
    dominate_required = EXCLUDED.dominate_required,
    dominate_allowed = EXCLUDED.dominate_allowed,
    non_dominate_role = EXCLUDED.non_dominate_role,
    non_dominate_required = EXCLUDED.non_dominate_required,
    non_dominate_allowed = EXCLUDED.non_dominate_allowed,
    non_dominate_recommended = EXCLUDED.non_dominate_recommended,
    non_dominate_role_highest_level_points = EXCLUDED.non_dominate_role_highest_level_points,
    non_dominate_role_highest_level = EXCLUDED.non_dominate_role_highest_level,
    valid_to = NULL,
    run_id = EXCLUDED.run_id;

-- Shared md5 signature for competitive role/division SCD2 (excludes dancer_name).

CREATE OR REPLACE FUNCTION core.dancer_roles_division_sig(
    dominate_role text,
    dominate_required text,
    dominate_allowed text,
    non_dominate_role text,
    non_dominate_required text,
    non_dominate_allowed text,
    non_dominate_recommended text,
    non_dominate_role_highest_level_points text,
    non_dominate_role_highest_level text
) RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
    SELECT md5(
        concat_ws('|',
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
    );
$$;

-- NULL as_of: current core name. Non-NULL: point-in-time from name history.
CREATE OR REPLACE FUNCTION core.dancer_name_at(p_dancer_id int, p_as_of date)
RETURNS text
LANGUAGE sql
STABLE
AS $$
    SELECT CASE
        WHEN p_as_of IS NULL THEN
            (SELECT d.dancer_name FROM core.dancers d WHERE d.dancer_id = p_dancer_id)
        ELSE COALESCE(
            (
                SELECT h.dancer_name
                FROM history.dancer_names_history h
                WHERE h.dancer_id = p_dancer_id
                  AND h.valid_from <= p_as_of
                  AND (h.valid_to IS NULL OR h.valid_to >= p_as_of)
                ORDER BY h.valid_from DESC
                LIMIT 1
            ),
            (SELECT d.dancer_name FROM core.dancers d WHERE d.dancer_id = p_dancer_id)
        )
    END;
$$;

CREATE OR REPLACE VIEW export.dancers_results_with_name AS
SELECT
    r.dancer_id,
    core.dancer_name_at(
        r.dancer_id,
        COALESCE(
            r.event_date,
            CASE
                WHEN r.event_year IS NOT NULL THEN make_date(
                    r.event_year,
                    GREATEST(1, LEAST(12, COALESCE(NULLIF(r.event_month, 0), 1))),
                    1
                )
            END
        )
    ) AS dancer_name,
    r.dance            AS event_dance,
    r.division         AS event_competition,
    LOWER(r.role)      AS event_role,
    r.result_raw       AS event_result,
    r.points           AS event_points,
    COALESCE(e.name, r.event_name_raw) AS event_name,
    r.location_id,
    r.event_year,
    r.event_month,
    r.event_date       AS event_year_and_month
FROM core.results r
LEFT JOIN core.events e ON e.event_id = r.event_id;

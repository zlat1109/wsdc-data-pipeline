-- Point-in-time dancer name lookup + split history export views.

CREATE OR REPLACE FUNCTION core.dancer_name_at(p_dancer_id int, p_as_of date)
RETURNS text
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(
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
    );
$$;

-- Division changes only; dancer_name is denormalized display (not a change trigger).
CREATE OR REPLACE VIEW export.changed_dancer_role_info AS
SELECT
    h.dancer_id,
    COALESCE(h.dancer_name, d.dancer_name) AS dancer_name,
    h.dominate_role,
    h.dominate_required,
    h.dominate_allowed,
    h.non_dominate_role,
    h.non_dominate_required,
    h.non_dominate_allowed,
    h.valid_from AS update_date,
    h.non_dominate_role_highest_level_points,
    h.non_dominate_role_highest_level,
    h.non_dominate_recommended
FROM history.dancer_roles_history h
LEFT JOIN core.dancers d ON d.dancer_id = h.dancer_id
ORDER BY h.dancer_id, h.valid_from;

-- Name-only change log (new Tableau contract).
CREATE OR REPLACE VIEW export.changed_dancer_name_info AS
SELECT
    dancer_id,
    dancer_name,
    valid_from AS update_date
FROM history.dancer_names_history
ORDER BY dancer_id, valid_from;

-- Optional: results with name as of event date (opt-in export).
CREATE OR REPLACE VIEW export.dancers_results_with_name AS
SELECT
    r.dancer_id,
    core.dancer_name_at(r.dancer_id, r.event_date) AS dancer_name,
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

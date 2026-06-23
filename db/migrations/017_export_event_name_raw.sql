-- Export: keep raw API event name when event_id is not resolved yet.

CREATE OR REPLACE VIEW export.dancers_results_info AS
SELECT
    r.dancer_id,
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

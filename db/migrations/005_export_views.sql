-- Export views: Tableau Public contract (old-laptop CSV format, full-word levels/roles).

CREATE SCHEMA IF NOT EXISTS export;

-- dancers_points_info.csv (6 columns)
CREATE OR REPLACE VIEW export.dancers_points_info AS
SELECT
    dancer_id,
    role,
    dance,
    level,
    total_points,
    update_date
FROM core.dancer_points;

-- dancer_role_info.csv (12 columns)
CREATE OR REPLACE VIEW export.dancer_role_info AS
SELECT
    dr.dancer_id,
    d.dancer_name,
    dr.dominate_role,
    dr.dominate_required,
    dr.dominate_allowed,
    dr.non_dominate_role,
    dr.non_dominate_required,
    dr.non_dominate_allowed,
    dr.non_dominate_recommended,
    dr.non_dominate_role_highest_level_points,
    dr.non_dominate_role_highest_level,
    dr.update_date
FROM core.dancer_roles dr
JOIN core.dancers d ON d.dancer_id = dr.dancer_id;

-- dancers_results_info.csv (11 columns — old-laptop order, no event_name_id)
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

-- location_info.csv (7 columns — old-laptop format)
CREATE OR REPLACE VIEW export.location_info AS
SELECT
    location_id,
    event_city,
    event_state,
    event_country,
    latitude,
    longitude,
    event_location
FROM core.locations;

-- events_wsdc.csv (5 columns — old-laptop format)
CREATE OR REPLACE VIEW export.events_wsdc AS
SELECT
    ei.event_id     AS id,
    e.name,
    ei.location_raw AS location,
    e.url,
    ei.date_raw     AS date
FROM core.event_instances ei
JOIN core.events e ON e.event_id = ei.event_id;

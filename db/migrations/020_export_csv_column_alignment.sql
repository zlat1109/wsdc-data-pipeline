-- Align export views with committed Tableau CSV column sets (parser-compatible extras).

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
    r.event_date       AS event_year_and_month,
    r.result_standardized AS event_result_standardized
FROM core.results r
LEFT JOIN core.events e ON e.event_id = r.event_id;

CREATE OR REPLACE VIEW export.location_info AS
SELECT
    location_id,
    event_city,
    event_state,
    event_country,
    latitude,
    longitude,
    event_location,
    event_location_standardized,
    coordinates_valid
FROM core.locations;

CREATE OR REPLACE VIEW export.events_wsdc AS
SELECT
    ei.event_id     AS id,
    e.name,
    ei.location_raw AS location,
    e.url,
    ei.date_raw     AS date,
    ei.event_date   AS parsed_date,
    ei.event_year,
    ei.event_month,
    CASE
        WHEN ei.event_year IS NOT NULL AND ei.event_month IS NOT NULL
            THEN to_char(make_date(ei.event_year, ei.event_month, 1), 'YYYY-MM')
        ELSE NULL
    END AS event_year_month
FROM core.event_instances ei
JOIN core.events e ON e.event_id = ei.event_id;

-- Geo-aware export views for Tableau event analytics.

CREATE OR REPLACE VIEW export.geo_events AS
WITH base AS (
    SELECT
        c.event_id,
        c.canonical_name AS display_name,
        c.typical_city,
        c.typical_state,
        c.typical_country,
        c.typical_location,
        c.url,
        c.registry_status,
        c.edition_count,
        c.total_result_rows,
        CASE
            WHEN c.typical_city IN ('Boston', 'Framingham')
                 AND c.typical_state = 'Massachusetts'
                 AND c.typical_country = 'United States'
                THEN 'metro:greater_boston_ma'
            ELSE lower(trim(coalesce(c.typical_city, '')))
                 || '|' || lower(trim(coalesce(c.typical_state, '')))
                 || '|' || lower(trim(coalesce(c.typical_country, '')))
        END AS geo_key,
        CASE
            WHEN c.typical_city IN ('Boston', 'Framingham')
                 AND c.typical_state = 'Massachusetts'
                 AND c.typical_country = 'United States'
                THEN 'Boston / Framingham, MA'
        END AS metro_label
    FROM core.event_catalog c
)
SELECT
    event_id,
    display_name,
    typical_city,
    typical_state,
    typical_country,
    typical_location,
    geo_key,
    lower(regexp_replace(display_name, '[^a-zA-Z0-9]+', '_', 'g'))
        || '::' || geo_key AS geo_event_key,
    metro_label,
    url,
    registry_status,
    edition_count,
    total_result_rows
FROM base;

CREATE OR REPLACE VIEW export.results_by_geo_event AS
SELECT
    r.result_id,
    r.dancer_id,
    r.event_id,
    ge.display_name AS event_name,
    ge.geo_event_key,
    ge.geo_key,
    ge.metro_label,
    ge.typical_city,
    ge.typical_state,
    ge.typical_country,
    ge.typical_location,
    ed.edition_id,
    r.event_year,
    r.event_month,
    r.event_date,
    ed.edition_date,
    ed.place_city,
    ed.place_state,
    ed.place_country,
    ed.location_raw AS edition_location,
    r.location_id,
    r.dance,
    r.division,
    r.role,
    r.result_raw,
    r.result_standardized,
    r.points,
    r.event_name_raw
FROM core.results r
LEFT JOIN export.geo_events ge ON ge.event_id = r.event_id
LEFT JOIN core.event_editions ed
    ON ed.event_id = r.event_id
   AND ed.event_year = r.event_year
   AND ed.event_month = r.event_month
WHERE r.event_id IS NOT NULL;

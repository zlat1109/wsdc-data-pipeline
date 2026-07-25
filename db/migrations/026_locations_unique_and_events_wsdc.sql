-- Stable location identity + authoritative events_wsdc export.
--
-- 1) Unique index on normalized event_location prevents two location_id values
--    for the same place string (the class of bugs fixed by LOCATION_ID_MERGE_MAP).
-- 2) export.events_wsdc switches from stale core.event_instances to
--    core.event_editions + core.locations (authoritative location_raw / FK).

CREATE UNIQUE INDEX IF NOT EXISTS locations_event_location_norm_uidx
    ON core.locations (lower(btrim(event_location)))
    WHERE event_location IS NOT NULL AND btrim(event_location) <> '';

CREATE OR REPLACE VIEW export.events_wsdc AS
SELECT
    ed.event_id AS id,
    e.name,
    COALESCE(NULLIF(btrim(l.event_location), ''), ed.location_raw) AS location,
    e.url,
    CASE
        WHEN ed.event_year IS NOT NULL AND ed.event_month IS NOT NULL
            THEN to_char(make_date(ed.event_year, ed.event_month, 1), 'FMMonth YYYY')
        ELSE NULL
    END AS date,
    ed.edition_date AS parsed_date,
    ed.event_year,
    ed.event_month,
    CASE
        WHEN ed.event_year IS NOT NULL AND ed.event_month IS NOT NULL
            THEN to_char(make_date(ed.event_year, ed.event_month, 1), 'YYYY-MM')
        ELSE NULL
    END AS event_year_month
FROM core.event_editions ed
JOIN core.events e ON e.event_id = ed.event_id
LEFT JOIN core.locations l ON l.location_id = ed.location_id;

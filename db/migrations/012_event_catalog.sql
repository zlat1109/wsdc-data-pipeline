-- Event catalog: brand-level metadata + year/month editions for Tableau / analytics.
-- Rebuilt after each points load (see db/build_event_catalog.py).
-- Join results: event_id + event_year + event_month = edition_key (or edition_id).

CREATE TABLE IF NOT EXISTS core.event_catalog (
    event_id              int PRIMARY KEY REFERENCES core.events (event_id),
    canonical_name        text NOT NULL,
    url                   text,
    registry_status       text,
    typical_city          text,
    typical_state         text,
    typical_country       text,
    typical_location      text,
    first_edition_year    int,
    last_edition_year     int,
    edition_count         int NOT NULL DEFAULT 0,
    total_result_rows     bigint NOT NULL DEFAULT 0,
    unique_dancers        int NOT NULL DEFAULT 0,
    upcoming_start_date   date,
    upcoming_location     text,
    updated_at            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.event_editions (
    edition_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id        int NOT NULL REFERENCES core.events (event_id),
    event_year      int NOT NULL,
    event_month     int NOT NULL,
    edition_date    date,
    location_id     int REFERENCES core.locations (location_id),
    place_city      text,
    place_state     text,
    place_country   text,
    location_raw    text,
    result_rows     int NOT NULL DEFAULT 0,
    unique_dancers  int NOT NULL DEFAULT 0,
    UNIQUE (event_id, event_year, event_month)
);

CREATE INDEX IF NOT EXISTS event_editions_event_idx
    ON core.event_editions (event_id);

CREATE INDEX IF NOT EXISTS event_editions_year_idx
    ON core.event_editions (event_year, event_month);

CREATE INDEX IF NOT EXISTS event_catalog_country_idx
    ON core.event_catalog (typical_country);

COMMENT ON TABLE core.event_catalog IS
    'One row per WSDC registry event (brand): URL, typical location, edition stats.';

COMMENT ON TABLE core.event_editions IS
    'One row per event held in a given year/month; join results on (event_id, event_year, event_month).';

-- Tableau: event catalog dashboard
CREATE OR REPLACE VIEW export.event_catalog AS
SELECT
    event_id,
    canonical_name,
    url,
    registry_status,
    typical_city,
    typical_state,
    typical_country,
    typical_location,
    first_edition_year,
    last_edition_year,
    edition_count,
    total_result_rows,
    unique_dancers,
    upcoming_start_date,
    upcoming_location,
    updated_at
FROM core.event_catalog
ORDER BY canonical_name;

-- Tableau: edition history per event
CREATE OR REPLACE VIEW export.event_editions AS
SELECT
    ed.edition_id,
    ed.event_id,
    c.canonical_name AS event_name,
    ed.event_year,
    ed.event_month,
    ed.edition_date,
    ed.location_id,
    ed.place_city,
    ed.place_state,
    ed.place_country,
    ed.location_raw,
    ed.result_rows,
    ed.unique_dancers,
    c.url,
    c.typical_location,
    c.registry_status
FROM core.event_editions ed
JOIN core.event_catalog c ON c.event_id = ed.event_id
ORDER BY ed.event_year DESC, ed.event_month DESC, c.canonical_name;

-- Tableau: results with event + edition context (event-centric analytics)
CREATE OR REPLACE VIEW export.results_by_event AS
SELECT
    r.result_id,
    r.dancer_id,
    r.event_id,
    c.canonical_name AS event_name,
    ed.edition_id,
    r.event_year,
    r.event_month,
    r.event_date,
    ed.edition_date,
    ed.place_city,
    ed.place_state,
    ed.place_country,
    ed.location_raw AS edition_location,
    c.typical_city,
    c.typical_state,
    c.typical_country,
    c.typical_location,
    c.url AS event_url,
    c.registry_status,
    r.location_id,
    r.dance,
    r.division,
    r.role,
    r.result_raw,
    r.result_standardized,
    r.points
FROM core.results r
LEFT JOIN core.event_catalog c ON c.event_id = r.event_id
LEFT JOIN core.event_editions ed
    ON ed.event_id = r.event_id
   AND ed.event_year = r.event_year
   AND ed.event_month = r.event_month
WHERE r.event_id IS NOT NULL;

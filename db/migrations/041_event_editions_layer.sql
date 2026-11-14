-- Event Editions enrichment from Todd Analytical Datasets (WSDC only).
-- Parallel attributes + status history; core.event_editions remains SoT for
-- occurred editions. Soft natural keys — no FK into promote_core truncates.

CREATE TABLE IF NOT EXISTS core.ee_loads (
    load_id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    loaded_at     timestamptz NOT NULL DEFAULT now(),
    source_file   text NOT NULL,
    file_sha256   text,
    built_at      text,
    git_commit    text,
    row_counts    jsonb NOT NULL DEFAULT '{}'::jsonb,
    match_stats   jsonb NOT NULL DEFAULT '{}'::jsonb
);

COMMENT ON TABLE core.ee_loads IS
    'One row per Event Editions parquet load into edition_attributes / status history.';

CREATE TABLE IF NOT EXISTS core.edition_attributes (
    event_id               int NOT NULL,
    event_year             int NOT NULL,
    event_month            int NOT NULL,
    todd_edition_id        text NOT NULL,
    match_kind             text NOT NULL
        CHECK (match_kind IN ('exact', 'merge_map', 'month_shift', 'unmatched')),
    venue_id               bigint,
    registry_status        text,
    scoring_software       text,
    coordinates_precision  text,
    date_precision         text,
    accommodation_hotel    text,
    wsdc_event_name        text,
    row_info               jsonb,
    load_id                bigint REFERENCES core.ee_loads (load_id),
    PRIMARY KEY (event_id, event_year, event_month)
);

CREATE UNIQUE INDEX IF NOT EXISTS edition_attributes_todd_id_uidx
    ON core.edition_attributes (todd_edition_id);
CREATE INDEX IF NOT EXISTS edition_attributes_venue_idx
    ON core.edition_attributes (venue_id);
CREATE INDEX IF NOT EXISTS edition_attributes_load_idx
    ON core.edition_attributes (load_id);

COMMENT ON TABLE core.edition_attributes IS
    'Todd Event Editions attributes for occurred WSDC editions (1:1 natural key). '
    'No FK to core.event_editions (promote_core TRUNCATE CASCADE).';

COMMENT ON COLUMN core.edition_attributes.venue_id IS
    'Soft FK to core.venues (added in 042); NULL until venues loaded.';

CREATE TABLE IF NOT EXISTS core.edition_status_history (
    event_id               int NOT NULL,
    event_year             int NOT NULL,
    event_month            int NOT NULL,
    todd_edition_id        text NOT NULL,
    edition_status         text NOT NULL
        CHECK (edition_status IN ('cancelled', 'hiatus', 'no_results')),
    cancelled_covid        boolean,
    event_edition_name     text,
    start_date             date,
    end_date               date,
    registry_status        text,
    city                   text,
    region                 text,
    country                text,
    load_id                bigint REFERENCES core.ee_loads (load_id),
    PRIMARY KEY (event_id, event_year, event_month)
);

CREATE UNIQUE INDEX IF NOT EXISTS edition_status_history_todd_id_uidx
    ON core.edition_status_history (todd_edition_id);
CREATE INDEX IF NOT EXISTS edition_status_history_status_idx
    ON core.edition_status_history (edition_status);
CREATE INDEX IF NOT EXISTS edition_status_history_load_idx
    ON core.edition_status_history (load_id);

COMMENT ON TABLE core.edition_status_history IS
    'WSDC editions that did not take place (cancelled / hiatus / no_results). '
    'Future scheduled editions stay in core.scheduled_events.';

CREATE OR REPLACE VIEW export.edition_attributes AS
SELECT
    a.event_id,
    a.event_year,
    a.event_month,
    a.todd_edition_id,
    a.match_kind,
    a.venue_id,
    a.registry_status,
    a.scoring_software,
    a.coordinates_precision,
    a.date_precision,
    a.accommodation_hotel,
    a.wsdc_event_name,
    a.row_info,
    a.load_id,
    ed.edition_id,
    ed.start_date,
    ed.end_date,
    ed.calendar_status,
    ed.location_id,
    ev.name AS event_name
FROM core.edition_attributes a
LEFT JOIN core.event_editions ed
  ON ed.event_id = a.event_id
 AND ed.event_year = a.event_year
 AND ed.event_month = a.event_month
LEFT JOIN core.events ev ON ev.event_id = a.event_id;

CREATE OR REPLACE VIEW export.edition_status_history AS
SELECT
    s.event_id,
    s.event_year,
    s.event_month,
    s.todd_edition_id,
    s.edition_status,
    s.cancelled_covid,
    s.event_edition_name,
    s.start_date,
    s.end_date,
    s.registry_status,
    s.city,
    s.region,
    s.country,
    s.load_id,
    ev.name AS event_name
FROM core.edition_status_history s
LEFT JOIN core.events ev ON ev.event_id = s.event_id;

DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'core.ee_loads',
    'core.edition_attributes',
    'core.edition_status_history'
  ]
  LOOP
    EXECUTE format('ALTER TABLE IF EXISTS %s ENABLE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;

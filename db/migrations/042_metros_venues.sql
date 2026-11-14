-- Metros + venues from Todd Event Editions; metro_id on core.locations.

CREATE TABLE IF NOT EXISTS core.metros (
    metro_id    int PRIMARY KEY,
    name        text NOT NULL,
    country     text,
    latitude    double precision,
    longitude   double precision
);

CREATE UNIQUE INDEX IF NOT EXISTS metros_name_country_uidx
    ON core.metros (lower(name), coalesce(lower(country), ''));

COMMENT ON TABLE core.metros IS
    'Metro areas from Todd Event Editions (cities within ~40 km grouped).';

ALTER TABLE core.locations
    ADD COLUMN IF NOT EXISTS metro_id int;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'locations_metro_id_fkey'
  ) THEN
    ALTER TABLE core.locations
      ADD CONSTRAINT locations_metro_id_fkey
      FOREIGN KEY (metro_id) REFERENCES core.metros (metro_id);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS locations_metro_idx ON core.locations (metro_id);

COMMENT ON COLUMN core.locations.metro_id IS
    'FK to core.metros; backfilled from Todd city→metro mapping.';

CREATE TABLE IF NOT EXISTS core.venues (
    venue_id         bigint PRIMARY KEY,
    name             text NOT NULL,
    name_normalized  text NOT NULL,
    address          text,
    venue_type       text,
    venue_url        text,
    latitude         double precision,
    longitude        double precision,
    location_id      int  -- soft FK to core.locations (promote-safe)
);

CREATE INDEX IF NOT EXISTS venues_name_norm_idx
    ON core.venues (name_normalized);
CREATE INDEX IF NOT EXISTS venues_location_idx
    ON core.venues (location_id);

COMMENT ON TABLE core.venues IS
    'Deduplicated venues from Todd Event Editions (normalized name + address).';

COMMENT ON COLUMN core.venues.location_id IS
    'Soft FK to core.locations — no DB FK (promote_core TRUNCATE CASCADE).';

CREATE OR REPLACE VIEW export.metros AS
SELECT metro_id, name, country, latitude, longitude
FROM core.metros;

CREATE OR REPLACE VIEW export.venues AS
SELECT
    v.venue_id,
    v.name,
    v.name_normalized,
    v.address,
    v.venue_type,
    v.venue_url,
    v.latitude,
    v.longitude,
    v.location_id,
    l.event_city,
    l.event_state,
    l.event_country
FROM core.venues v
LEFT JOIN core.locations l ON l.location_id = v.location_id;

-- REPLACE VIEW cannot rename/reorder columns; drop first.
DROP VIEW IF EXISTS export.edition_attributes;
CREATE VIEW export.edition_attributes AS
SELECT
    a.event_id,
    a.event_year,
    a.event_month,
    a.todd_edition_id,
    a.match_kind,
    a.venue_id,
    v.name AS venue_name,
    v.venue_type,
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
    m.metro_id,
    m.name AS metro,
    ev.name AS event_name
FROM core.edition_attributes a
LEFT JOIN core.venues v ON v.venue_id = a.venue_id
LEFT JOIN core.event_editions ed
  ON ed.event_id = a.event_id
 AND ed.event_year = a.event_year
 AND ed.event_month = a.event_month
LEFT JOIN core.locations l ON l.location_id = ed.location_id
LEFT JOIN core.metros m ON m.metro_id = l.metro_id
LEFT JOIN core.events ev ON ev.event_id = a.event_id;

DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['core.metros', 'core.venues']
  LOOP
    EXECUTE format('ALTER TABLE IF EXISTS %s ENABLE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;

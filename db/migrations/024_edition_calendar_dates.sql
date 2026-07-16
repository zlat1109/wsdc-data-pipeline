-- Durable day-precision dates from WSDC Events Calendar (+ optional list backfill).
-- Survives TRUNCATE of core.event_editions; re-applied in rebuild_event_catalog.
-- @docs-summary: Edition calendar dates archive + start/end on event_editions export

ALTER TABLE core.event_editions
    ADD COLUMN IF NOT EXISTS start_date date,
    ADD COLUMN IF NOT EXISTS end_date date,
    ADD COLUMN IF NOT EXISTS date_source text,
    ADD COLUMN IF NOT EXISTS calendar_status text,
    ADD COLUMN IF NOT EXISTS event_occurred boolean;

COMMENT ON COLUMN core.event_editions.start_date IS
    'Inclusive first day from WSDC calendar/list; NULL when hiatus/cancelled or unknown.';
COMMENT ON COLUMN core.event_editions.end_date IS
    'Inclusive last day from WSDC calendar/list; NULL when hiatus/cancelled or unknown.';
COMMENT ON COLUMN core.event_editions.date_source IS
    'wsdc_calendar | wsdc_events_list';
COMMENT ON COLUMN core.event_editions.calendar_status IS
    'scheduled | unconfirmed | hiatus | cancelled';
COMMENT ON COLUMN core.event_editions.event_occurred IS
    'TRUE when edition has results and calendar status is not hiatus/cancelled.';

CREATE TABLE IF NOT EXISTS core.edition_calendar_dates (
    event_id             int NOT NULL REFERENCES core.events (event_id),
    event_year           int NOT NULL,
    event_month          int NOT NULL,
    planned_start_date   date,
    planned_end_date     date,
    calendar_status      text NOT NULL DEFAULT 'scheduled'
        CHECK (calendar_status IN ('scheduled', 'unconfirmed', 'hiatus', 'cancelled')),
    date_source          text NOT NULL DEFAULT 'wsdc_calendar',
    source_fingerprint   text,
    calendar_title       text,
    url                  text,
    match_via            text,
    scraped_at           timestamptz,
    updated_at           timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (event_id, event_year, event_month)
);

CREATE INDEX IF NOT EXISTS edition_calendar_dates_start_idx
    ON core.edition_calendar_dates (planned_start_date);

CREATE INDEX IF NOT EXISTS edition_calendar_dates_status_idx
    ON core.edition_calendar_dates (calendar_status);

COMMENT ON TABLE core.edition_calendar_dates IS
    'Planned edition dates from worldsdc.com/events/calendar/ (and list backfill). '
    'Not truncated by points load; copied onto event_editions after each rebuild.';

DROP VIEW IF EXISTS export.event_editions;
CREATE VIEW export.event_editions AS
SELECT
    ed.edition_id,
    ed.event_id,
    c.canonical_name AS event_name,
    ed.event_year,
    ed.event_month,
    ed.edition_date,
    ed.start_date,
    ed.end_date,
    ed.date_source,
    ed.calendar_status,
    ed.event_occurred,
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

DROP VIEW IF EXISTS export.edition_calendar_dates;
CREATE VIEW export.edition_calendar_dates AS
SELECT
    d.event_id,
    c.canonical_name AS event_name,
    d.event_year,
    d.event_month,
    d.planned_start_date,
    d.planned_end_date,
    d.calendar_status,
    d.date_source,
    d.source_fingerprint,
    d.calendar_title,
    d.url,
    d.match_via,
    d.scraped_at,
    d.updated_at
FROM core.edition_calendar_dates d
LEFT JOIN core.event_catalog c ON c.event_id = d.event_id
ORDER BY d.planned_start_date DESC NULLS LAST, c.canonical_name;

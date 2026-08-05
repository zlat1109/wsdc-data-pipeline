-- Trial / list geo: attach location_id (+ provenance) to schedule rows.
-- Additive only — does not rewrite existing core.locations coverage.
-- Source priority (app-enforced): event_website > events_list > points.

ALTER TABLE core.scheduled_events
    ADD COLUMN IF NOT EXISTS location_id int REFERENCES core.locations (location_id),
    ADD COLUMN IF NOT EXISTS location_source text;

ALTER TABLE core.events_list_current
    ADD COLUMN IF NOT EXISTS location_id int REFERENCES core.locations (location_id),
    ADD COLUMN IF NOT EXISTS location_source text;

CREATE INDEX IF NOT EXISTS scheduled_events_location_id_idx
    ON core.scheduled_events (location_id)
    WHERE location_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS events_list_current_location_id_idx
    ON core.events_list_current (location_id)
    WHERE location_id IS NOT NULL;

COMMENT ON COLUMN core.scheduled_events.location_id IS
    'Resolved place for this edition (trial/list geo). Null until ensure_location runs.';
COMMENT ON COLUMN core.scheduled_events.location_source IS
    'Provenance: location_info | city_canonical | google_maps | event_website | unresolved';
COMMENT ON COLUMN core.events_list_current.location_id IS
    'Resolved place for nearest upcoming edition (copied from scheduled_events).';
COMMENT ON COLUMN core.events_list_current.location_source IS
    'Provenance for location_id (same vocabulary as scheduled_events.location_source).';

-- Edition archive export
DROP VIEW IF EXISTS export.scheduled_event_editions;

CREATE VIEW export.scheduled_event_editions AS
SELECT
    source_fingerprint,
    event_name,
    original_date,
    start_date,
    end_date,
    results_year,
    results_month,
    location_raw,
    country,
    country_flag,
    url,
    status_event,
    status_event AS registry_trial_status,
    location_id,
    location_source,
    confirmed,
    canceled,
    on_hiatus,
    is_active,
    first_seen_at,
    last_seen_at
FROM core.scheduled_events
WHERE is_active = true
ORDER BY start_date, event_name;

-- Brand-level Tableau / analytics export
DROP VIEW IF EXISTS export.scheduled_events;

CREATE VIEW export.scheduled_events AS
SELECT
    schedule_event_key,
    source_fingerprint,
    canonical_event_id,
    event_name,
    canonical_name,
    original_date,
    start_date,
    end_date,
    results_year,
    results_month,
    location_raw,
    country,
    country_flag,
    url,
    status_event,
    status_event AS registry_trial_status,
    location_id,
    location_source,
    confirmed,
    canceled,
    on_hiatus,
    match_status,
    match_method,
    match_confidence,
    upcoming_editions,
    updated_at
FROM core.events_list_current
ORDER BY start_date, event_name;

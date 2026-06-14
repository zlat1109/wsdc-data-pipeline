-- Split schedule storage:
--   core.scheduled_events     = edition-level archive (source_fingerprint, incl. history)
--   core.events_list_current  = one row per logical event (nearest upcoming edition)
--   history.*                 = run + added/removed logs (unchanged)

CREATE TABLE IF NOT EXISTS core.events_list_current (
    schedule_event_key   text PRIMARY KEY,
    source_fingerprint   text NOT NULL,
    canonical_event_id   int,
    event_name           text NOT NULL,
    canonical_name       text,
    original_date        text,
    start_date           date,
    end_date             date,
    results_year         int,
    results_month        int,
    location_raw         text,
    country              text,
    country_flag         text,
    url                  text,
    status_event         text,
    confirmed            boolean DEFAULT true,
    canceled             boolean DEFAULT false,
    on_hiatus            boolean DEFAULT false,
    match_status         text,
    match_method         text,
    match_confidence     double precision,
    upcoming_editions    int NOT NULL DEFAULT 1,
    updated_at           timestamptz NOT NULL DEFAULT now(),
    last_run_id          int REFERENCES history.events_list_runs (run_id)
);

CREATE INDEX IF NOT EXISTS events_list_current_start_idx
    ON core.events_list_current (start_date);

CREATE INDEX IF NOT EXISTS events_list_current_event_id_idx
    ON core.events_list_current (canonical_event_id);

CREATE INDEX IF NOT EXISTS events_list_current_fingerprint_idx
    ON core.events_list_current (source_fingerprint);

COMMENT ON TABLE core.scheduled_events IS
    'Edition-level schedule archive keyed by source_fingerprint (all scrape observations).';

COMMENT ON TABLE core.events_list_current IS
    'Latest schedule snapshot: one row per logical event (nearest upcoming edition).';

-- All active editions still on the site (multi-year listings).
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
    confirmed,
    canceled,
    on_hiatus,
    is_active,
    first_seen_at,
    last_seen_at
FROM core.scheduled_events
WHERE is_active = true
ORDER BY start_date, event_name;

-- Tableau / analytics: one row per event brand.
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

-- WSDC Events List: upcoming schedule + weekly change log.
-- Independent from points load (promote_core does NOT truncate these tables).

CREATE SCHEMA IF NOT EXISTS export;

CREATE TABLE IF NOT EXISTS history.events_list_runs (
    run_id         serial PRIMARY KEY,
    scraped_at     timestamptz NOT NULL DEFAULT now(),
    source         text NOT NULL DEFAULT 'github-actions',
    total_events   int  NOT NULL DEFAULT 0,
    added_count    int  NOT NULL DEFAULT 0,
    removed_count  int  NOT NULL DEFAULT 0,
    unchanged_count int NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS core.scheduled_events (
    source_fingerprint text PRIMARY KEY,
    event_name         text NOT NULL,
    original_date      text,
    start_date         date,
    end_date           date,
    results_year       int,
    results_month      int,
    location_raw       text,
    country            text,
    country_flag       text,
    url                text,
    status_event       text,
    confirmed          boolean DEFAULT true,
    canceled           boolean DEFAULT false,
    on_hiatus          boolean DEFAULT false,
    is_active          boolean DEFAULT true,
    first_seen_at      timestamptz NOT NULL DEFAULT now(),
    last_seen_at       timestamptz NOT NULL DEFAULT now(),
    last_run_id        int REFERENCES history.events_list_runs (run_id)
);

CREATE INDEX IF NOT EXISTS scheduled_events_active_idx
    ON core.scheduled_events (is_active, start_date);

CREATE INDEX IF NOT EXISTS scheduled_events_start_idx
    ON core.scheduled_events (start_date);

CREATE TABLE IF NOT EXISTS history.events_list_changes (
    change_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id             int NOT NULL REFERENCES history.events_list_runs (run_id),
    change_type        text NOT NULL CHECK (change_type IN ('added', 'removed')),
    source_fingerprint text NOT NULL,
    event_name         text,
    start_date         date,
    end_date           date,
    location_raw       text,
    url                text,
    snapshot           jsonb
);

CREATE INDEX IF NOT EXISTS events_list_changes_run_idx
    ON history.events_list_changes (run_id);

-- Tableau / export
CREATE OR REPLACE VIEW export.scheduled_events AS
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
    url,
    status_event,
    confirmed,
    canceled,
    on_hiatus,
    is_active,
    first_seen_at,
    last_seen_at
FROM core.scheduled_events
WHERE is_active = true
ORDER BY start_date, event_name;

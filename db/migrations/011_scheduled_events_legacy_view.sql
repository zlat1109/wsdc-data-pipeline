-- Legacy Tableau view: one row per active edition (pre-009 schema shape).
-- Use export.scheduled_events for one row per event brand.

DROP VIEW IF EXISTS export.scheduled_events_legacy;

CREATE VIEW export.scheduled_events_legacy AS
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

COMMENT ON VIEW export.scheduled_events_legacy IS
    'Deprecated Tableau source: all active editions. Prefer export.scheduled_events (one row per event).';

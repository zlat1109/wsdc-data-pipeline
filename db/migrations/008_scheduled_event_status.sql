-- Ensure status_event is always Registry Event or Trial Event on the export surface.

UPDATE core.scheduled_events
SET status_event = 'Registry Event'
WHERE COALESCE(TRIM(status_event), '') = ''
   OR status_event NOT IN ('Registry Event', 'Trial Event');

DROP VIEW IF EXISTS export.scheduled_events;

CREATE VIEW export.scheduled_events AS
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

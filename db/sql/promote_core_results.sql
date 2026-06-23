-- Results promote (run after seed_event_aliases + seed_result_only_events).

INSERT INTO core.results (
    dancer_id, event_id, location_id, dance, division, role,
    event_year, event_month, event_date, result_raw, result_standardized, points,
    event_name_raw
)
SELECT
    s.dancer_id::int,
    COALESCE(
        NULLIF(TRIM(s.event_name_id), '')::int,
        ev.event_id,
        ea.event_id
    ),
    NULLIF(TRIM(s.location_id), '')::int,
    NULLIF(TRIM(s.event_dance), ''),
    NULLIF(TRIM(s.event_competition), ''),
    CASE LOWER(TRIM(s.event_role))
        WHEN 'leader' THEN 'Leader'
        WHEN 'follower' THEN 'Follower'
    END,
    NULLIF(TRIM(s.event_year), '')::int,
    NULLIF(TRIM(s.event_month), '')::int,
    CASE
        WHEN NULLIF(TRIM(s.event_year_and_month), '') ~ '^\d{4}-\d{2}-\d{2}$'
            THEN NULLIF(TRIM(s.event_year_and_month), '')::date
        ELSE NULL
    END,
    NULLIF(TRIM(s.event_result), ''),
    NULLIF(TRIM(s.event_result_standardized), ''),
    COALESCE(NULLIF(TRIM(s.event_points), '')::int, 0),
    NULLIF(TRIM(s.event_name), '')
FROM staging.dancers_results_info s
LEFT JOIN (
    SELECT name, MIN(event_id) AS event_id
    FROM core.events
    GROUP BY name
) ev ON ev.name = NULLIF(TRIM(s.event_name), '')
LEFT JOIN core.event_aliases ea ON ea.alias = NULLIF(TRIM(s.event_name), '')
WHERE s.dancer_id ~ '^\d+$'
  AND CASE LOWER(TRIM(s.event_role)) WHEN 'leader' THEN 'Leader' WHEN 'follower' THEN 'Follower' END IS NOT NULL;

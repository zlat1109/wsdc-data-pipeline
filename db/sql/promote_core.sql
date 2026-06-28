-- Promote staging -> core (run after CSV load into staging).
-- Expects canonical normalization via JOIN on core.levels + role title-case.

-- Preserve names before truncate so empty API responses do not wipe known names.
CREATE TEMP TABLE _preserved_dancer_names AS
SELECT dancer_id, dancer_name FROM core.dancers;

-- Clear core data (keep levels dictionary).
TRUNCATE
    core.results,
    core.dancer_points,
    core.dancer_roles,
    core.event_instances,
    core.event_aliases,
    core.events,
    core.locations,
    core.dancers
RESTART IDENTITY CASCADE;

-- Dancers: every ID referenced in role/points/results (name may be NULL — WSDC allows blank names)
INSERT INTO core.dancers (dancer_id, dancer_name)
SELECT
    ids.dancer_id,
    COALESCE(names.dancer_name, prev.dancer_name) AS dancer_name
FROM (
    SELECT dancer_id::int AS dancer_id
    FROM staging.dancer_role_info
    WHERE dancer_id ~ '^\d+$'
    UNION
    SELECT dancer_id::int
    FROM staging.dancers_points_info
    WHERE dancer_id ~ '^\d+$'
    UNION
    SELECT dancer_id::int
    FROM staging.dancers_results_info
    WHERE dancer_id ~ '^\d+$'
) ids
LEFT JOIN (
    SELECT DISTINCT ON (dancer_id::int)
        dancer_id::int AS dancer_id,
        NULLIF(TRIM(dancer_name), '') AS dancer_name
    FROM staging.dancer_role_info
    WHERE dancer_id ~ '^\d+$'
    ORDER BY dancer_id::int, NULLIF(TRIM(dancer_name), '') NULLS LAST
) names ON names.dancer_id = ids.dancer_id
LEFT JOIN _preserved_dancer_names prev ON prev.dancer_id = ids.dancer_id;

-- Locations
INSERT INTO core.locations (
    location_id, event_city, event_state, event_country,
    latitude, longitude, event_location, event_location_standardized, coordinates_valid
)
SELECT
    location_id::int,
    NULLIF(TRIM(event_city), ''),
    NULLIF(TRIM(event_state), ''),
    NULLIF(TRIM(event_country), ''),
    NULLIF(TRIM(latitude), '')::numeric,
    NULLIF(TRIM(longitude), '')::numeric,
    NULLIF(TRIM(event_location), ''),
    NULLIF(TRIM(event_location_standardized), ''),
    CASE LOWER(TRIM(coordinates_valid))
        WHEN 'true' THEN true WHEN 'false' THEN false ELSE NULL
    END
FROM staging.location_info
WHERE location_id ~ '^\d+$';

-- Events (catalog)
INSERT INTO core.events (event_id, name, url)
SELECT DISTINCT ON (id::int)
    id::int,
    TRIM(name),
    NULLIF(TRIM(url), '')
FROM staging.events_wsdc
WHERE id ~ '^\d+$'
ORDER BY id::int, event_instance_id::int;

-- Event instances (parser CSV has event_instance_id; export CSV uses synthetic ids)
INSERT INTO core.event_instances (
    event_instance_id, event_id, location_id, location_raw,
    date_raw, event_date, event_year, event_month
)
SELECT
    COALESCE(
        NULLIF(TRIM(event_instance_id), '')::int,
        ROW_NUMBER() OVER (ORDER BY id::int, NULLIF(TRIM(date), ''))::int
    ),
    id::int,
    NULL,
    NULLIF(TRIM(location), ''),
    NULLIF(TRIM(date), ''),
    NULLIF(TRIM(parsed_date), '')::date,
    NULLIF(TRIM(event_year), '')::int,
    NULLIF(TRIM(event_month), '')::int
FROM staging.events_wsdc
WHERE id ~ '^\d+$';

-- Events referenced in results but absent from events_wsdc catalog
INSERT INTO core.events (event_id, name, url)
SELECT
    s.event_name_id::int,
    MAX(NULLIF(TRIM(s.event_name), '')),
    NULL
FROM staging.dancers_results_info s
WHERE s.event_name_id ~ '^\d+$'
  AND NOT EXISTS (
      SELECT 1 FROM core.events e WHERE e.event_id = s.event_name_id::int
  )
GROUP BY s.event_name_id::int;

-- Dancer points (current snapshot)
INSERT INTO core.dancer_points (dancer_id, role, dance, level, total_points, update_date)
SELECT
    s.dancer_id::int,
    CASE LOWER(TRIM(s.role))
        WHEN 'leader' THEN 'Leader'
        WHEN 'follower' THEN 'Follower'
        ELSE INITCAP(TRIM(s.role))
    END,
    TRIM(s.dance),
    COALESCE(l.level, TRIM(s.level)),
    COALESCE(NULLIF(TRIM(s.total_points), '')::int, 0),
    NULLIF(TRIM(s.update_date), '')::date
FROM staging.dancers_points_info s
LEFT JOIN core.levels l
    ON UPPER(TRIM(s.level)) = l.level_abbr OR TRIM(s.level) = l.level
WHERE s.dancer_id ~ '^\d+$'
  AND CASE LOWER(TRIM(s.role)) WHEN 'leader' THEN 'Leader' WHEN 'follower' THEN 'Follower' END IS NOT NULL
  AND COALESCE(l.level, TRIM(s.level)) IN (SELECT level FROM core.levels);

-- Dancer roles (current snapshot)
INSERT INTO core.dancer_roles (
    dancer_id, dominate_role, dominate_required, dominate_allowed,
    non_dominate_role, non_dominate_required, non_dominate_allowed,
    non_dominate_recommended, non_dominate_role_highest_level_points,
    non_dominate_role_highest_level, update_date
)
SELECT
    s.dancer_id::int,
    NULLIF(TRIM(s.dominate_role), ''),
    COALESCE(l1.level, TRIM(s.dominate_required)),
    COALESCE(l2.level, TRIM(s.dominate_allowed)),
    NULLIF(TRIM(s.non_dominate_role), ''),
    COALESCE(l3.level, TRIM(s.non_dominate_required)),
    COALESCE(l4.level, TRIM(s.non_dominate_allowed)),
    COALESCE(l5.level, TRIM(s.non_dominate_recommended)),
    NULLIF(TRIM(s.non_dominate_role_highest_level_points), ''),
    COALESCE(l6.level, TRIM(s.non_dominate_role_highest_level)),
    NULLIF(TRIM(s.update_date), '')::date
FROM staging.dancer_role_info s
LEFT JOIN core.levels l1 ON UPPER(TRIM(s.dominate_required)) = l1.level_abbr OR TRIM(s.dominate_required) = l1.level
LEFT JOIN core.levels l2 ON UPPER(TRIM(s.dominate_allowed)) = l2.level_abbr OR TRIM(s.dominate_allowed) = l2.level
LEFT JOIN core.levels l3 ON UPPER(TRIM(s.non_dominate_required)) = l3.level_abbr OR TRIM(s.non_dominate_required) = l3.level
LEFT JOIN core.levels l4 ON UPPER(TRIM(s.non_dominate_allowed)) = l4.level_abbr OR TRIM(s.non_dominate_allowed) = l4.level
LEFT JOIN core.levels l5 ON UPPER(TRIM(s.non_dominate_recommended)) = l5.level_abbr OR TRIM(s.non_dominate_recommended) = l5.level
LEFT JOIN core.levels l6 ON UPPER(TRIM(s.non_dominate_role_highest_level)) = l6.level_abbr OR TRIM(s.non_dominate_role_highest_level) = l6.level
WHERE s.dancer_id ~ '^\d+$';

-- Results promoted in promote_core_results.sql after event alias seeding.

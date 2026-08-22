-- Audit event_id ↔ location_id links for completed editions (run before/after MV refresh).
-- Paste into Supabase SQL Editor. Each block is independent.

-- ---------------------------------------------------------------------------
-- 0) Summary counts (completed = has results, not hiatus/cancelled, in the past)
-- ---------------------------------------------------------------------------
WITH completed AS (
    SELECT
        ed.*,
        COALESCE(
            ed.end_date,
            cal.planned_end_date,
            (
                DATE_TRUNC(
                    'month',
                    MAKE_DATE(ed.event_year, ed.event_month, 1)
                ) + INTERVAL '1 month - 1 day'
            )::date
        ) AS sort_end_date
    FROM core.event_editions ed
    LEFT JOIN core.edition_calendar_dates cal
      ON cal.event_id = ed.event_id
     AND cal.event_year = ed.event_year
     AND cal.event_month = ed.event_month
    WHERE ed.result_rows > 0
      AND COALESCE(ed.calendar_status, 'scheduled')
          NOT IN ('hiatus', 'cancelled')
      AND COALESCE(
            ed.end_date,
            cal.planned_end_date,
            (
                DATE_TRUNC(
                    'month',
                    MAKE_DATE(ed.event_year, ed.event_month, 1)
                ) + INTERVAL '1 month - 1 day'
            )::date
          ) < CURRENT_DATE
)
SELECT
    count(*)                                                   AS completed_editions,
    count(*) FILTER (WHERE location_id IS NULL)                AS null_location_id,
    count(*) FILTER (
        WHERE location_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM core.locations l
              WHERE l.location_id = completed.location_id
          )
    )                                                          AS orphan_location_id
FROM completed;

-- ---------------------------------------------------------------------------
-- 1) Registry country ≠ edition place_country (should be 0)
-- ---------------------------------------------------------------------------
WITH completed AS (
    SELECT ed.*
    FROM core.event_editions ed
    LEFT JOIN core.edition_calendar_dates cal
      ON cal.event_id = ed.event_id
     AND cal.event_year = ed.event_year
     AND cal.event_month = ed.event_month
    WHERE ed.result_rows > 0
      AND COALESCE(ed.calendar_status, 'scheduled')
          NOT IN ('hiatus', 'cancelled')
      AND COALESCE(
            ed.end_date,
            cal.planned_end_date,
            (
                DATE_TRUNC(
                    'month',
                    MAKE_DATE(ed.event_year, ed.event_month, 1)
                ) + INTERVAL '1 month - 1 day'
            )::date
          ) < CURRENT_DATE
)
SELECT
    c.event_id,
    cat.canonical_name AS event_name,
    c.event_year,
    c.event_month,
    c.edition_id,
    c.location_id,
    l.event_country    AS registry_country,
    c.place_country    AS edition_place_country,
    l.event_city       AS registry_city,
    c.place_city       AS edition_place_city
FROM completed c
JOIN core.event_catalog cat ON cat.event_id = c.event_id
JOIN core.locations l ON l.location_id = c.location_id
WHERE c.place_country IS NOT NULL
  AND l.event_country IS NOT NULL
  AND lower(btrim(l.event_country)) <> lower(btrim(c.place_country))
ORDER BY c.event_year DESC, cat.canonical_name
LIMIT 200;

-- ---------------------------------------------------------------------------
-- 2) Same event_id → multiple countries across completed editions (series moves?)
-- ---------------------------------------------------------------------------
WITH completed AS (
    SELECT ed.event_id, ed.location_id
    FROM core.event_editions ed
    LEFT JOIN core.edition_calendar_dates cal
      ON cal.event_id = ed.event_id
     AND cal.event_year = ed.event_year
     AND cal.event_month = ed.event_month
    WHERE ed.result_rows > 0
      AND COALESCE(ed.calendar_status, 'scheduled')
          NOT IN ('hiatus', 'cancelled')
      AND COALESCE(
            ed.end_date,
            cal.planned_end_date,
            (
                DATE_TRUNC(
                    'month',
                    MAKE_DATE(ed.event_year, ed.event_month, 1)
                ) + INTERVAL '1 month - 1 day'
            )::date
          ) < CURRENT_DATE
),
per_event AS (
    SELECT
        c.event_id,
        l.event_country,
        count(*) AS edition_count
    FROM completed c
    JOIN core.locations l ON l.location_id = c.location_id
    WHERE l.event_country IS NOT NULL
    GROUP BY c.event_id, l.event_country
)
SELECT
    p.event_id,
    cat.canonical_name AS event_name,
    count(DISTINCT p.event_country) AS distinct_countries,
    string_agg(
        p.event_country || ' (' || p.edition_count || ')',
        ', ' ORDER BY p.event_country
    ) AS countries
FROM per_event p
JOIN core.event_catalog cat ON cat.event_id = p.event_id
GROUP BY p.event_id, cat.canonical_name
HAVING count(DISTINCT p.event_country) > 1
ORDER BY distinct_countries DESC, cat.canonical_name;

-- ---------------------------------------------------------------------------
-- 3) Catalog typical_country ≠ mode country on completed editions
-- ---------------------------------------------------------------------------
WITH completed AS (
    SELECT ed.event_id, ed.location_id
    FROM core.event_editions ed
    LEFT JOIN core.edition_calendar_dates cal
      ON cal.event_id = ed.event_id
     AND cal.event_year = ed.event_year
     AND cal.event_month = ed.event_month
    WHERE ed.result_rows > 0
      AND COALESCE(ed.calendar_status, 'scheduled')
          NOT IN ('hiatus', 'cancelled')
      AND COALESCE(
            ed.end_date,
            cal.planned_end_date,
            (
                DATE_TRUNC(
                    'month',
                    MAKE_DATE(ed.event_year, ed.event_month, 1)
                ) + INTERVAL '1 month - 1 day'
            )::date
          ) < CURRENT_DATE
),
mode_country AS (
    SELECT
        c.event_id,
        mode() WITHIN GROUP (ORDER BY l.event_country) AS mode_country,
        count(*) AS n
    FROM completed c
    JOIN core.locations l ON l.location_id = c.location_id
    WHERE l.event_country IS NOT NULL
    GROUP BY c.event_id
)
SELECT
    cat.event_id,
    cat.canonical_name,
    cat.typical_country,
    m.mode_country,
    m.n AS completed_editions
FROM core.event_catalog cat
JOIN mode_country m ON m.event_id = cat.event_id
WHERE cat.typical_country IS NOT NULL
  AND lower(btrim(cat.typical_country)) <> lower(btrim(m.mode_country))
ORDER BY cat.canonical_name;

-- ---------------------------------------------------------------------------
-- 4) Edition location_id ≠ results majority location_id (recent years)
-- ---------------------------------------------------------------------------
WITH completed AS (
    SELECT
        ed.event_id,
        ed.event_year,
        ed.event_month,
        ed.edition_id,
        ed.location_id AS edition_location_id,
        (
            SELECT r.location_id
            FROM core.results r
            WHERE r.event_id = ed.event_id
              AND r.event_year = ed.event_year
              AND r.event_month = ed.event_month
              AND r.location_id IS NOT NULL
            GROUP BY r.location_id
            ORDER BY count(*) DESC, r.location_id
            LIMIT 1
        ) AS results_location_id
    FROM core.event_editions ed
    WHERE ed.result_rows > 0
      AND ed.event_year >= 2020
      AND COALESCE(ed.calendar_status, 'scheduled')
          NOT IN ('hiatus', 'cancelled')
)
SELECT
    c.event_id,
    cat.canonical_name AS event_name,
    c.event_year,
    c.event_month,
    c.edition_id,
    c.edition_location_id,
    le.event_city || ', ' || coalesce(le.event_state || ', ', '') || le.event_country
        AS edition_location,
    c.results_location_id,
    lr.event_city || ', ' || coalesce(lr.event_state || ', ', '') || lr.event_country
        AS results_location
FROM completed c
JOIN core.event_catalog cat ON cat.event_id = c.event_id
LEFT JOIN core.locations le ON le.location_id = c.edition_location_id
LEFT JOIN core.locations lr ON lr.location_id = c.results_location_id
WHERE c.edition_location_id IS NOT NULL
  AND c.results_location_id IS NOT NULL
  AND c.edition_location_id <> c.results_location_id
ORDER BY c.event_year DESC, cat.canonical_name
LIMIT 200;

-- ---------------------------------------------------------------------------
-- 5) location_raw drift vs core.locations (from quality_checks)
-- ---------------------------------------------------------------------------
SELECT
    ed.event_id,
    cat.canonical_name AS event_name,
    ed.event_year,
    ed.event_month,
    ed.edition_id,
    ed.location_id,
    ed.location_raw,
    l.event_location AS registry_location
FROM core.event_editions ed
JOIN core.event_catalog cat ON cat.event_id = ed.event_id
JOIN core.locations l ON l.location_id = ed.location_id
WHERE ed.result_rows > 0
  AND ed.location_raw IS NOT NULL
  AND btrim(ed.location_raw) <> ''
  AND lower(btrim(l.event_location)) <> lower(btrim(ed.location_raw))
  AND lower(btrim(l.event_location)) NOT LIKE lower(btrim(ed.location_raw)) || ',%'
ORDER BY ed.event_year DESC, cat.canonical_name
LIMIT 200;

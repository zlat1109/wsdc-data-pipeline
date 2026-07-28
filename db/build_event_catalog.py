"""Rebuild core.event_catalog and core.event_editions from core + schedule."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from catalog_registry import apply_catalog_registry_cleanup

_REBUILD_EDITIONS_SQL = """
INSERT INTO core.event_editions (
    event_id, event_year, event_month, edition_date,
    location_id, place_city, place_state, place_country, location_raw,
    result_rows, unique_dancers
)
WITH base AS (
    SELECT
        r.event_id,
        r.event_year,
        r.event_month,
        MIN(r.event_date) AS edition_date,
        COUNT(*)::int AS result_rows,
        COUNT(DISTINCT r.dancer_id)::int AS unique_dancers
    FROM core.results r
    WHERE r.event_id IS NOT NULL
      AND r.event_year IS NOT NULL
      AND r.event_month IS NOT NULL
    GROUP BY r.event_id, r.event_year, r.event_month
),
event_urls AS (
    SELECT event_id, NULLIF(TRIM(url), '') AS event_url
    FROM core.events
),
schedule_loc_rank AS (
    SELECT
        b.event_id,
        b.event_year,
        b.event_month,
        s.location_raw,
        ROW_NUMBER() OVER (
            PARTITION BY b.event_id, b.event_year, b.event_month
            ORDER BY COALESCE(s.is_active, false) DESC, s.last_seen_at DESC NULLS LAST, s.first_seen_at DESC NULLS LAST
        ) AS rn
    FROM base b
    JOIN event_urls eu
      ON eu.event_id = b.event_id
     AND eu.event_url IS NOT NULL
    JOIN core.scheduled_events s
      ON lower(btrim(s.url)) = lower(btrim(eu.event_url))
     AND s.results_year = b.event_year
     AND s.results_month = b.event_month
     AND s.location_raw IS NOT NULL
     AND btrim(s.location_raw) <> ''
),
schedule_loc AS (
    SELECT
        event_id,
        event_year,
        event_month,
        location_raw
    FROM schedule_loc_rank
    WHERE rn = 1
),
schedule_loc_mapped AS (
    SELECT
        sl.event_id,
        sl.event_year,
        sl.event_month,
        l.location_id,
        l.event_city,
        l.event_state,
        l.event_country,
        COALESCE(l.event_location_standardized, l.event_location) AS location_raw
    FROM schedule_loc sl
    LEFT JOIN core.locations l
      ON lower(btrim(l.event_location)) = lower(btrim(sl.location_raw))
      OR (
        l.event_location_standardized IS NOT NULL
        AND lower(btrim(l.event_location_standardized)) = lower(btrim(sl.location_raw))
      )
),
loc_rank AS (
    SELECT
        r.event_id,
        r.event_year,
        r.event_month,
        r.location_id,
        COUNT(*) AS cnt,
        ROW_NUMBER() OVER (
            PARTITION BY r.event_id, r.event_year, r.event_month
            ORDER BY COUNT(*) DESC, r.location_id
        ) AS rn
    FROM core.results r
    WHERE r.event_id IS NOT NULL
      AND r.event_year IS NOT NULL
      AND r.event_month IS NOT NULL
      AND r.location_id IS NOT NULL
    GROUP BY r.event_id, r.event_year, r.event_month, r.location_id
),
top_loc AS (
    SELECT event_id, event_year, event_month, location_id
    FROM loc_rank
    WHERE rn = 1
)
SELECT
    b.event_id,
    b.event_year,
    b.event_month,
    b.edition_date,
    COALESCE(slm.location_id, tl.location_id),
    COALESCE(slm.event_city, l.event_city),
    COALESCE(slm.event_state, l.event_state),
    COALESCE(slm.event_country, l.event_country),
    COALESCE(
        slm.location_raw,
        COALESCE(l.event_location_standardized, l.event_location)
    ),
    b.result_rows,
    b.unique_dancers
FROM base b
LEFT JOIN top_loc tl
    ON tl.event_id = b.event_id
   AND tl.event_year = b.event_year
   AND tl.event_month = b.event_month
LEFT JOIN schedule_loc_mapped slm
    ON slm.event_id = b.event_id
   AND slm.event_year = b.event_year
   AND slm.event_month = b.event_month
LEFT JOIN core.locations l ON l.location_id = tl.location_id
"""

_REBUILD_CATALOG_SQL = """
INSERT INTO core.event_catalog (
    event_id, canonical_name, url, registry_status,
    typical_city, typical_state, typical_country, typical_location,
    first_edition_year, last_edition_year, edition_count,
    total_result_rows, unique_dancers, updated_at
)
WITH edition_stats AS (
    SELECT
        event_id,
        MIN(event_year) AS first_edition_year,
        MAX(event_year) AS last_edition_year,
        COUNT(*)::int AS edition_count,
        SUM(result_rows)::bigint AS total_result_rows,
        SUM(unique_dancers)::int AS sum_dancers
    FROM core.event_editions
    GROUP BY event_id
),
dancer_counts AS (
    SELECT event_id, COUNT(DISTINCT dancer_id)::int AS unique_dancers
    FROM core.results
    WHERE event_id IS NOT NULL
    GROUP BY event_id
),
recent_edition AS (
    SELECT DISTINCT ON (event_id)
        event_id,
        place_city,
        place_state,
        place_country,
        location_raw
    FROM core.event_editions
    ORDER BY event_id, event_year DESC, event_month DESC
)
SELECT
    e.event_id,
    e.name,
    NULLIF(TRIM(e.url), ''),
    NULL,
    re.place_city,
    re.place_state,
    re.place_country,
    re.location_raw,
    es.first_edition_year,
    es.last_edition_year,
    COALESCE(es.edition_count, 0),
    COALESCE(es.total_result_rows, 0),
    COALESCE(dc.unique_dancers, 0),
    now()
FROM core.events e
LEFT JOIN edition_stats es ON es.event_id = e.event_id
LEFT JOIN dancer_counts dc ON dc.event_id = e.event_id
LEFT JOIN recent_edition re ON re.event_id = e.event_id
"""

_ENRICH_FROM_SCHEDULE_SQL = """
UPDATE core.event_catalog c
SET
    registry_status = COALESCE(s.status_event, c.registry_status),
    url = COALESCE(NULLIF(TRIM(s.url), ''), c.url),
    upcoming_start_date = s.start_date,
    upcoming_location = s.location_raw,
    updated_at = now()
FROM core.events_list_current s
WHERE s.canonical_event_id = c.event_id
"""

_ENRICH_FROM_KNOWN_SQL = """
UPDATE core.event_catalog c
SET
    canonical_name = COALESCE(NULLIF(%s, ''), c.canonical_name),
    url = COALESCE(NULLIF(%s, ''), c.url),
    typical_location = COALESCE(NULLIF(%s, ''), c.typical_location),
    updated_at = now()
WHERE c.event_id = %s
"""


def rebuild_event_catalog(conn: Any) -> tuple[int, int]:
    """Truncate and rebuild catalog + editions. Returns (catalog_count, edition_count)."""
    from transform.knowledge import KNOWN_EVENT_METADATA

    now = datetime.now(timezone.utc)

    with conn.cursor() as cur:
        cur.execute("TRUNCATE core.event_editions")
        cur.execute("TRUNCATE core.event_catalog")

        cur.execute(_REBUILD_EDITIONS_SQL)
        edition_count = cur.rowcount

        cur.execute(_REBUILD_CATALOG_SQL)
        catalog_count = cur.rowcount

        # Events with zero results still deserve a catalog row if on schedule
        cur.execute(
            """
            INSERT INTO core.event_catalog (event_id, canonical_name, url, updated_at)
            SELECT e.event_id, e.name, NULLIF(TRIM(e.url), ''), %s
            FROM core.events e
            WHERE NOT EXISTS (
                SELECT 1 FROM core.event_catalog c WHERE c.event_id = e.event_id
            )
            """,
            (now,),
        )
        catalog_count += cur.rowcount

        cur.execute(_ENRICH_FROM_SCHEDULE_SQL)

        from edition_calendar import enrich_event_editions_dates

        enrich_event_editions_dates(conn)

        for event_id, meta in KNOWN_EVENT_METADATA.items():
            typical = meta.get("typical_location") or ""
            loc = meta.get("location") or {}
            if isinstance(loc, dict) and loc.get("event_location"):
                typical = loc["event_location"]
            cur.execute(
                _ENRICH_FROM_KNOWN_SQL,
                (
                    meta.get("name") or "",
                    meta.get("url") or "",
                    typical,
                    event_id,
                ),
            )

        cur.execute("SELECT COUNT(*) FROM core.event_catalog")
        catalog_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM core.event_editions")
        edition_count = cur.fetchone()[0]

    apply_catalog_registry_cleanup(conn)

    return catalog_count, edition_count

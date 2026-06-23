"""Seed core.event_aliases and result-only events before results promote."""

from __future__ import annotations

from typing import Any

from transform.knowledge.event_aliases import (
    RESULT_TO_CATALOG_EVENT_NAME,
    build_event_name_normalization,
)


def seed_event_aliases(conn: Any) -> int:
    """Insert alias → event_id rows from knowledge maps. Returns rows upserted."""
    normalization = build_event_name_normalization()
    count = 0
    with conn.cursor() as cur:
        for alias, canonical in normalization.items():
            if alias == canonical:
                continue
            cur.execute(
                """
                INSERT INTO core.event_aliases (alias, event_id)
                SELECT %s, MIN(e.event_id)
                FROM core.events e
                WHERE e.name = %s
                HAVING COUNT(*) > 0
                ON CONFLICT (alias) DO UPDATE
                SET event_id = EXCLUDED.event_id
                """,
                (alias, canonical),
            )
            count += cur.rowcount
    return count


def seed_result_only_events(conn: Any) -> int:
    """Create core.events rows for normalized names absent from events_wsdc."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO core.events (event_id, name, url)
            SELECT
                base.max_id + ROW_NUMBER() OVER (ORDER BY o.name),
                o.name,
                NULL
            FROM (
                SELECT DISTINCT NULLIF(TRIM(s.event_name), '') AS name
                FROM staging.dancers_results_info s
                WHERE NULLIF(TRIM(s.event_name), '') IS NOT NULL
            ) o
            CROSS JOIN (SELECT COALESCE(MAX(event_id), 0) AS max_id FROM core.events) base
            WHERE NOT EXISTS (
                SELECT 1 FROM core.events e WHERE e.name = o.name
            )
            """
        )
        return cur.rowcount


def prepare_event_resolution(conn: Any) -> tuple[int, int]:
    """Seed aliases + orphan events. Returns (alias_count, orphan_event_count)."""
    alias_count = seed_event_aliases(conn)
    orphan_count = seed_result_only_events(conn)
    return alias_count, orphan_count

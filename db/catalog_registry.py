"""Registry overlay for core.event_catalog after rebuild (phantom merges, inactive rows)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Ghost / duplicate WSDC registry ids → canonical event_id.
# Keys are empty catalog rows (0 results). Values must be live series with results.
# Re-check after WSDC reuses ids — wrong targets create dangerous name aliases.
PHANTOM_ALIAS_TO_CANONICAL: dict[int, int] = {
    # MADjam spelling/branding ghosts → Mid-Atlantic Dance Jam
    440: 92,
    443: 92,
    # Midnight Madness branding ghosts → Midnight Madness (Dallas)
    444: 288,
    445: 288,
    # Kazan title ghost (not Swing & Snow)
    467: 283,
    # UK WCS title ghosts → UK WCS Championships (London)
    486: 154,
    487: 154,
    # USA Grand Nationals title ghosts → USA Grand Nationals (Atlanta)
    488: 22,
    489: 22,
    490: 22,
    # SwingTime Denver list/registry ghost → Swingtime points id (Denver)
    466: 47,
}


def _apply_phantom_aliases(cur: Any, phantom_map: dict[int, int]) -> None:
    for phantom_id, canonical_id in phantom_map.items():
        cur.execute("SELECT name FROM core.events WHERE event_id = %s", (phantom_id,))
        row = cur.fetchone()
        if row and row[0]:
            cur.execute(
                """
                INSERT INTO core.event_aliases (alias, event_id)
                VALUES (%s, %s)
                ON CONFLICT (alias) DO UPDATE SET event_id = EXCLUDED.event_id
                """,
                (str(row[0]).strip(), canonical_id),
            )
        cur.execute(
            """
            UPDATE core.event_catalog
            SET registry_status = 'merged', updated_at = now()
            WHERE event_id = %s
            """,
            (phantom_id,),
        )


def ensure_operator_provisional_catalog(conn: Any) -> int:
    """Upsert catalog stubs for calendar operator provisional event_ids.

    Soul Flow uses ``SOUL_FLOW_PROVISIONAL_EVENT_ID`` (990001) until WSDC assigns a
    real registry id. Without a catalog row, ``edition_calendar_orphan_event_ids``
    warns on every quality pass after operator calendar upserts.
    """
    from transform.knowledge.calendar_operator_overrides import (
        CALENDAR_OPERATOR_OVERRIDES,
    )

    by_id: dict[int, dict[str, Any]] = {}
    for row in CALENDAR_OPERATOR_OVERRIDES:
        eid = int(row["event_id"])
        # Real WSDC ids already come from results/schedule rebuild.
        if eid < 900000:
            continue
        title = str(row.get("calendar_title") or "").strip()
        # Prefer non-hiatus title when multiple operator rows share an id.
        prev = by_id.get(eid)
        if prev is None or (
            "hiatus" in str(prev.get("calendar_title") or "").lower()
            and "hiatus" not in title.lower()
        ):
            by_id[eid] = row

    if not by_id:
        return 0

    now = datetime.now(timezone.utc)
    n = 0
    with conn.cursor() as cur:
        for eid, row in sorted(by_id.items()):
            title = str(row.get("calendar_title") or "").strip()
            # Strip " (Hiatus -- YYYY)" marketing suffix for catalog display.
            if " (Hiatus" in title:
                title = title.split(" (Hiatus", 1)[0].strip()
            city = row.get("city")
            country = row.get("country")
            typical_location = None
            if city and country:
                typical_location = f"{city}, {country}"
            elif city or country:
                typical_location = city or country
            cur.execute(
                """
                INSERT INTO core.events (event_id, name, url)
                VALUES (%s, %s, %s)
                ON CONFLICT (event_id) DO UPDATE SET
                    name = COALESCE(
                        NULLIF(EXCLUDED.name, ''),
                        core.events.name
                    ),
                    url = COALESCE(
                        NULLIF(EXCLUDED.url, ''),
                        core.events.url
                    )
                """,
                (
                    eid,
                    title or f"Provisional event {eid}",
                    row.get("url"),
                ),
            )
            cur.execute(
                """
                INSERT INTO core.event_catalog (
                    event_id, canonical_name, url, registry_status,
                    typical_city, typical_country, typical_location, updated_at
                ) VALUES (
                    %s, %s, %s, 'provisional',
                    %s, %s, %s, %s
                )
                ON CONFLICT (event_id) DO UPDATE SET
                    canonical_name = COALESCE(
                        NULLIF(EXCLUDED.canonical_name, ''),
                        core.event_catalog.canonical_name
                    ),
                    url = COALESCE(
                        NULLIF(EXCLUDED.url, ''),
                        core.event_catalog.url
                    ),
                    registry_status = CASE
                        WHEN core.event_catalog.registry_status IN (
                            'inactive', 'merged'
                        )
                        THEN core.event_catalog.registry_status
                        ELSE 'provisional'
                    END,
                    typical_city = COALESCE(
                        NULLIF(EXCLUDED.typical_city, ''),
                        core.event_catalog.typical_city
                    ),
                    typical_country = COALESCE(
                        NULLIF(EXCLUDED.typical_country, ''),
                        core.event_catalog.typical_country
                    ),
                    typical_location = COALESCE(
                        NULLIF(EXCLUDED.typical_location, ''),
                        core.event_catalog.typical_location
                    ),
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    eid,
                    title or f"Provisional event {eid}",
                    row.get("url"),
                    city,
                    country,
                    typical_location,
                    now,
                ),
            )
            n += cur.rowcount
    return n


def apply_catalog_registry_cleanup(conn: Any) -> None:
    """Re-apply phantom merges and inactive flags after catalog rebuild."""
    with conn.cursor() as cur:
        _apply_phantom_aliases(cur, PHANTOM_ALIAS_TO_CANONICAL)
        phantom_ids = list(PHANTOM_ALIAS_TO_CANONICAL.keys())
        cur.execute(
            """
            UPDATE core.event_catalog
            SET registry_status = 'inactive', updated_at = now()
            WHERE total_result_rows = 0
              AND coalesce(registry_status, '') NOT IN (
                  'inactive', 'merged', 'provisional'
              )
              AND NOT (event_id = ANY(%s))
              AND event_id < 900000
            """,
            (phantom_ids,),
        )
        cur.execute("ANALYZE core.event_catalog, core.event_editions")
    ensure_operator_provisional_catalog(conn)

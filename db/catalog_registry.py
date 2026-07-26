"""Registry overlay for core.event_catalog after rebuild (phantom merges, inactive rows)."""

from __future__ import annotations

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
              AND coalesce(registry_status, '') NOT IN ('inactive', 'merged')
              AND NOT (event_id = ANY(%s))
            """,
            (phantom_ids,),
        )
        cur.execute("ANALYZE core.event_catalog, core.event_editions")

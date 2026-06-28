#!/usr/bin/env python3
"""Mark inactive catalog rows and alias phantom USA Grand Nationals ids.

Usage:
    python scripts/cleanup_event_catalog.py --dry-run
    python scripts/cleanup_event_catalog.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from build_event_catalog import rebuild_event_catalog  # noqa: E402
from connection import connect  # noqa: E402

PHANTOM_ALIAS_TO_CANONICAL = {
    486: 22,
    487: 22,
    488: 22,
    467: 215,  # Swing&Snow — registry spelling variant of Swing & Snow
}


def _apply_phantom_aliases(cur, phantom_map: dict[int, int]) -> None:
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT count(*) FROM core.event_catalog
                WHERE total_result_rows = 0
                  AND coalesce(registry_status, '') NOT IN ('inactive', 'merged')
                """
            )
            empty_count = int(cur.fetchone()[0])
            print(f"Empty catalog rows to mark inactive: {empty_count}")
            print(f"Phantom id aliases: {PHANTOM_ALIAS_TO_CANONICAL}")

            if args.dry_run:
                print("\nDry run — no changes applied.")
                return

            rebuild_event_catalog(conn)

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
        conn.commit()

    print("\nCatalog cleanup complete.")


if __name__ == "__main__":
    main()

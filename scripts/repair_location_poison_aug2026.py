#!/usr/bin/env python3
"""Remap shared-wrong location_ids for NZ / Philly / Montreal / DCSX / Nordic.

Live DB kept poison lids on raw WSDC titles that missed EVENT_NAME_LOCATION_OVERRIDES
exact-name match, and Nordic sat on Swing Fiction Brno (266) instead of Stockholm.

Usage:
    python scripts/repair_location_poison_aug2026.py --dry-run
    python scripts/repair_location_poison_aug2026.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

# (event_id, from_lid, to_lid, label)
RESULT_REMAPS: list[tuple[int, int, int, str]] = [
    (179, 253, 168, "NZ Open: Perth → Auckland"),
    (234, 222, 66, "Philly: St. Pete → Wilmington"),
    (178, 243, 86, "Montreal: São Paulo → Montreal"),
    (181, 13, 38, "DCSX: Washington → Herndon"),
    # Brno 266 is Swing Fiction; Nordic is Stockholm (Scandic Infra City).
    (253, 266, 199, "Nordic: Brno → Stockholm"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.dry_run == args.apply:
        print("Specify exactly one of --dry-run or --apply")
        return 2

    from connection import connect

    with connect() as conn:
        with conn.cursor() as cur:
            print("=== Current poison counts ===")
            for event_id, from_lid, to_lid, label in RESULT_REMAPS:
                cur.execute(
                    """
                    SELECT count(*) FROM core.results
                    WHERE event_id = %s AND location_id = %s
                    """,
                    (event_id, from_lid),
                )
                n = cur.fetchone()[0]
                print(f"  {label}: event_id={event_id} lid {from_lid}→{to_lid}: {n} rows")

            cur.execute(
                """
                SELECT event_year, event_month, location_id, count(*)
                FROM core.edition_location_baseline
                WHERE event_id = 253
                GROUP BY 1, 2, 3
                ORDER BY 1 DESC, 2 DESC
                """
            )
            print("  Nordic baseline lids:", cur.fetchall())

            if args.dry_run:
                print("dry-run only — no writes")
                return 0

            for event_id, from_lid, to_lid, label in RESULT_REMAPS:
                cur.execute(
                    """
                    UPDATE core.results
                    SET location_id = %s
                    WHERE event_id = %s AND location_id = %s
                    """,
                    (to_lid, event_id, from_lid),
                )
                print(f"  results {label}: {cur.rowcount}")
                cur.execute(
                    """
                    UPDATE core.event_editions
                    SET location_id = %s
                    WHERE event_id = %s AND location_id = %s
                    """,
                    (to_lid, event_id, from_lid),
                )
                print(f"  editions {label}: {cur.rowcount}")
                cur.execute(
                    """
                    UPDATE core.edition_location_baseline
                    SET location_id = %s,
                        source = 'manual',
                        updated_at = now()
                    WHERE event_id = %s AND location_id = %s
                    """,
                    (to_lid, event_id, from_lid),
                )
                print(f"  baseline {label}: {cur.rowcount}")

            # Nordic: shared Swing Fiction Brno (266) → Stockholm (199).
            # Earlier mistaken "confirm Brno" path is inverted here.
            cur.execute(
                """
                UPDATE core.edition_location_baseline
                SET location_id = 199,
                    source = 'manual',
                    updated_at = now()
                WHERE event_id = 253 AND location_id IS DISTINCT FROM 199
                """
            )
            print(f"  Nordic baseline → Stockholm 199: {cur.rowcount}")

            # Keep catalog typicals aligned for remapped series.
            cur.execute(
                """
                UPDATE core.event_catalog
                SET typical_city = 'Auckland', typical_state = NULL,
                    typical_country = 'New Zealand',
                    typical_location = 'Auckland, New Zealand'
                WHERE event_id = 179
                """
            )
            cur.execute(
                """
                UPDATE core.event_catalog
                SET typical_city = 'Wilmington', typical_state = 'Delaware',
                    typical_country = 'United States',
                    typical_location = 'Wilmington, DE, United States'
                WHERE event_id = 234
                """
            )
            cur.execute(
                """
                UPDATE core.event_catalog
                SET typical_city = 'Montreal', typical_state = NULL,
                    typical_country = 'Canada',
                    typical_location = 'Montreal, Canada'
                WHERE event_id = 178
                """
            )
            cur.execute(
                """
                UPDATE core.event_catalog
                SET typical_city = 'Herndon', typical_state = 'Virginia',
                    typical_country = 'United States',
                    typical_location = 'Herndon, VA, United States'
                WHERE event_id = 181
                """
            )
            cur.execute(
                """
                UPDATE core.event_catalog
                SET typical_city = 'Stockholm', typical_state = NULL,
                    typical_country = 'Sweden',
                    typical_location = 'Stockholm, Sweden'
                WHERE event_id = 253
                """
            )
            print("  catalog typicals refreshed for 179/234/178/181/253")

        conn.commit()
        print("OK — committed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

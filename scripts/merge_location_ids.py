#!/usr/bin/env python3
"""Merge duplicate core.locations rows to canonical location_id values.

Usage:
    python scripts/merge_location_ids.py --dry-run
    python scripts/merge_location_ids.py --apply
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
from transform.knowledge.locations import LOCATION_ID_MERGE_MAP  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not LOCATION_ID_MERGE_MAP:
        print("LOCATION_ID_MERGE_MAP is empty — nothing to do.")
        return

    with connect() as conn:
        with conn.cursor() as cur:
            for old_id, new_id in sorted(
                LOCATION_ID_MERGE_MAP.items(), key=lambda x: int(x[0])
            ):
                cur.execute(
                    "SELECT count(*) FROM core.results WHERE location_id = %s",
                    (int(old_id),),
                )
                results = int(cur.fetchone()[0])
                cur.execute(
                    "SELECT count(*) FROM core.event_editions WHERE location_id = %s",
                    (int(old_id),),
                )
                editions = int(cur.fetchone()[0])
                cur.execute(
                    "SELECT event_location FROM core.locations WHERE location_id = %s",
                    (int(old_id),),
                )
                row = cur.fetchone()
                label = row[0] if row else "(missing)"
                print(
                    f"  {old_id} → {new_id}: {results:,} results, "
                    f"{editions:,} editions — {label!r}"
                )

        if args.dry_run:
            print("\nDry run — no changes applied.")
            return

        with conn.cursor() as cur:
            for old_id, new_id in LOCATION_ID_MERGE_MAP.items():
                oid, nid = int(old_id), int(new_id)
                cur.execute(
                    "UPDATE core.results SET location_id = %s WHERE location_id = %s",
                    (nid, oid),
                )
                cur.execute(
                    "UPDATE core.event_editions SET location_id = %s WHERE location_id = %s",
                    (nid, oid),
                )
                cur.execute(
                    "UPDATE core.event_instances SET location_id = %s WHERE location_id = %s",
                    (nid, oid),
                )
                cur.execute(
                    "DELETE FROM core.locations WHERE location_id = %s",
                    (oid,),
                )
            catalog_count, edition_count = rebuild_event_catalog(conn)
            cur.execute("ANALYZE core.results, core.event_editions, core.event_catalog")
        conn.commit()

    print(
        f"\nMerge complete. Event catalog: {catalog_count:,} events, "
        f"{edition_count:,} editions."
    )


if __name__ == "__main__":
    main()

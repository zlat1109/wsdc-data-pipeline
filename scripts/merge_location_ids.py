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
from transform.geography.constants import us_country_sql_in_clause  # noqa: E402
from transform.knowledge.locations import (  # noqa: E402
    LOCATION_ID_CORRECTIONS,
    LOCATION_ID_MERGE_MAP,
)

FK_TABLES = (
    ("core.results", "location_id"),
    ("core.event_editions", "location_id"),
    ("core.event_instances", "location_id"),
)

_NUMERIC_COLUMNS = frozenset({"latitude", "longitude"})

_US_COUNTRY_SQL = us_country_sql_in_clause()


def _count_refs(conn, location_id: int) -> dict[str, int]:
    counts: dict[str, int] = {}
    with conn.cursor() as cur:
        for table, col in FK_TABLES:
            cur.execute(
                f"SELECT count(*) FROM {table} WHERE {col} = %s",
                (location_id,),
            )
            counts[table] = int(cur.fetchone()[0])
    return counts


def apply_location_id_corrections(conn) -> int:
    """Apply explicit field patches to canonical location rows."""
    if not LOCATION_ID_CORRECTIONS:
        return 0
    updated = 0
    with conn.cursor() as cur:
        for location_id, patch in sorted(LOCATION_ID_CORRECTIONS.items()):
            columns = list(patch.keys())
            db_values = [None if patch[col] == "" else patch[col] for col in columns]
            assignments: list[str] = []
            distinct: list[str] = []
            for col in columns:
                cast = "::numeric" if col in _NUMERIC_COLUMNS else ""
                assignments.append(f"{col} = %s{cast}")
                distinct.append(f"{col} IS DISTINCT FROM %s{cast}")
            cur.execute(
                f"""
                UPDATE core.locations
                SET {", ".join(assignments)}
                WHERE location_id = %s
                  AND ({" OR ".join(distinct)})
                """,
                db_values + [location_id] + db_values,
            )
            updated += cur.rowcount
    return updated


def clear_non_us_event_states(conn) -> int:
    """event_state is only meaningful for United States rows."""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE core.locations
            SET event_state = NULL
            WHERE event_state IS NOT NULL
              AND TRIM(event_state::text) <> ''
              AND COALESCE(TRIM(event_country::text), '') NOT IN ({_US_COUNTRY_SQL})
            """
        )
        return cur.rowcount


def apply_merges(conn) -> int:
    """Remap FKs and delete merged location rows; return rows touched."""
    changed = 0
    with conn.cursor() as cur:
        for old_id, new_id in LOCATION_ID_MERGE_MAP.items():
            oid, nid = int(old_id), int(new_id)
            for table, col in FK_TABLES:
                cur.execute(
                    f"UPDATE {table} SET {col} = %s WHERE {col} = %s",
                    (nid, oid),
                )
                changed += cur.rowcount
            cur.execute(
                "DELETE FROM core.locations WHERE location_id = %s",
                (oid,),
            )
            changed += cur.rowcount
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not LOCATION_ID_MERGE_MAP and not LOCATION_ID_CORRECTIONS:
        print("No location merge map or corrections configured.")
        return

    with connect() as conn:
        print("Merges (old → canonical):")
        for old_id, new_id in sorted(
            LOCATION_ID_MERGE_MAP.items(), key=lambda x: int(x[0])
        ):
            refs = _count_refs(conn, int(old_id))
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT event_location FROM core.locations WHERE location_id = %s",
                    (int(old_id),),
                )
                row = cur.fetchone()
            label = row[0] if row else "(missing)"
            ref_total = sum(refs.values())
            print(
                f"  {old_id} → {new_id}: {ref_total:,} refs "
                f"(results={refs['core.results']:,}) — {label!r}"
            )

        print(f"\nField corrections: {len(LOCATION_ID_CORRECTIONS)} location_id(s)")

        if args.dry_run:
            print("\nDry run — no changes applied.")
            return

        merge_changed = apply_merges(conn)
        corrected = apply_location_id_corrections(conn)
        cleared = clear_non_us_event_states(conn)
        catalog_count = edition_count = 0
        if merge_changed or corrected or cleared:
            catalog_count, edition_count = rebuild_event_catalog(conn)
        else:
            print("\nNo location changes — skipped catalog rebuild.")
        with conn.cursor() as cur:
            cur.execute(
                "ANALYZE core.results, core.event_editions, core.event_catalog, core.locations"
            )
        conn.commit()

    print(
        f"\nMerge complete: fk_rows={merge_changed:,}, corrections={corrected:,}, "
        f"non_us_states_cleared={cleared:,}, "
        f"catalog={catalog_count:,} events, {edition_count:,} editions."
    )


if __name__ == "__main__":
    main()

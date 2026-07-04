#!/usr/bin/env python3
"""Remove duplicate core.results rows and collapse duplicate core.locations in-place.

Does not re-parse WSDC; uses the same rules as preprocess dedupe (PR #14).

Usage:
    python scripts/dedupe_core_data.py --dry-run
    python scripts/dedupe_core_data.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from build_event_catalog import rebuild_event_catalog  # noqa: E402
from connection import connect  # noqa: E402
from transform.geography.resolve import dedupe_location_info  # noqa: E402

RESULT_DEDUP_COLS = (
    "dancer_id",
    "event_id",
    "location_id",
    "dance",
    "division",
    "role",
    "event_year",
    "event_month",
    "result_raw",
    "points",
)


def _load_locations(conn) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT location_id, event_city, event_state, event_country,
                   latitude, longitude, event_location, event_location_standardized,
                   coordinates_valid
            FROM core.locations
            ORDER BY location_id
            """
        )
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=cols)
    return df.astype(str).replace({"None": ""})


def _load_result_location_ids(conn) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute("SELECT result_id, location_id FROM core.results")
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=cols)
    df["location_id"] = df["location_id"].astype(str).replace({"None": "", "<NA>": ""})
    return df


def _count_duplicate_results(conn) -> int:
    cols = ", ".join(RESULT_DEDUP_COLS)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT COALESCE(SUM(cnt - 1), 0)::int
            FROM (
                SELECT COUNT(*) AS cnt
                FROM core.results
                GROUP BY {cols}
                HAVING COUNT(*) > 1
            ) d
            """
        )
        return int(cur.fetchone()[0])


def _delete_duplicate_results(conn) -> int:
    cols = ", ".join(RESULT_DEDUP_COLS)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            WITH ranked AS (
                SELECT result_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY {cols}
                           ORDER BY result_id
                       ) AS rn
                FROM core.results
            )
            DELETE FROM core.results r
            USING ranked x
            WHERE r.result_id = x.result_id
              AND x.rn > 1
            """
        )
        return cur.rowcount


def _apply_location_remap(conn, id_remap: dict[str, str]) -> None:
    if not id_remap:
        return
    with conn.cursor() as cur:
        for old_id, new_id in id_remap.items():
            oid, nid = int(old_id), int(new_id)
            cur.execute(
                "UPDATE core.results SET location_id = %s WHERE location_id = %s",
                (nid, oid),
            )
            cur.execute(
                "UPDATE core.event_instances SET location_id = %s WHERE location_id = %s",
                (nid, oid),
            )
            cur.execute(
                "UPDATE core.event_editions SET location_id = %s WHERE location_id = %s",
                (nid, oid),
            )


def _delete_location_ids(conn, drop_ids: set[str]) -> int:
    if not drop_ids:
        return 0
    ids = [int(x) for x in drop_ids]
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM core.locations WHERE location_id = ANY(%s)",
            (ids,),
        )
        return cur.rowcount


def plan_location_dedupe(conn) -> tuple[dict[str, str], set[str], int, int]:
    locations = _load_locations(conn)
    results = _load_result_location_ids(conn)
    before_loc = len(locations)

    out_results, deduped_locations, merged = dedupe_location_info(results, locations)

    id_remap: dict[str, str] = {}
    for idx in results.index:
        old_id = str(results.at[idx, "location_id"]).strip()
        new_id = str(out_results.at[idx, "location_id"]).strip()
        if old_id and new_id and old_id != new_id:
            id_remap[old_id] = new_id

    old_ids = set(locations["location_id"].astype(str).str.strip())
    new_ids = set(deduped_locations["location_id"].astype(str).str.strip())
    drop_ids = old_ids - new_ids

    return id_remap, drop_ids, before_loc, len(deduped_locations)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    with connect() as conn:
        dup_results = _count_duplicate_results(conn)
        id_remap, drop_ids, loc_before, loc_after = plan_location_dedupe(conn)

        print("Planned changes:")
        print(f"  core.results: delete {dup_results:,} duplicate row(s)")
        print(f"  core.locations: {loc_before:,} → {loc_after:,} rows ({len(drop_ids):,} removed)")
        print(f"  location_id remap: {len(id_remap):,} old id(s) → canonical id(s)")

        if args.dry_run:
            print("\nDry run — no changes applied.")
            return

        if dup_results == 0 and not id_remap and not drop_ids:
            print("\nNo duplicate results or locations — skipped apply.")
            return

        deleted = _delete_duplicate_results(conn)
        _apply_location_remap(conn, id_remap)
        removed = _delete_location_ids(conn, drop_ids)
        catalog_count, edition_count = rebuild_event_catalog(conn)
        with conn.cursor() as cur:
            cur.execute(
                "ANALYZE core.results, core.locations, core.event_editions, core.event_catalog"
            )
        conn.commit()

    print(
        f"\nDedupe complete: results_deleted={deleted:,}, "
        f"locations_removed={removed:,}, "
        f"catalog={catalog_count:,} events, {edition_count:,} editions."
    )


if __name__ == "__main__":
    main()

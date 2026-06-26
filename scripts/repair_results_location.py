#!/usr/bin/env python3
"""Repair core.results.location_id without full backfill.

Reloads results CSV into staging, re-promotes core.results, rebuilds event catalog.
Does not touch history.* or core dancer_points / dancer_roles snapshots.

Usage:
    python scripts/repair_results_location.py
    python scripts/repair_results_location.py --data-dir "/path/to/csv"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from build_event_catalog import rebuild_event_catalog  # noqa: E402
from connection import connect  # noqa: E402
from enrich_known_events import enrich_core_known_events  # noqa: E402
from seed_event_aliases import prepare_event_resolution  # noqa: E402
from staging_loader import copy_csv, load_staging_from_dir  # noqa: E402


def read_sql(name: str) -> str:
    return (PROJECT_ROOT / "db" / "sql" / name).read_text(encoding="utf-8")


_SYNC_LOCATIONS_SQL = """
INSERT INTO core.locations (
    location_id, event_city, event_state, event_country,
    latitude, longitude, event_location, event_location_standardized, coordinates_valid
)
SELECT
    location_id::int,
    NULLIF(TRIM(event_city), ''),
    NULLIF(TRIM(event_state), ''),
    NULLIF(TRIM(event_country), ''),
    NULLIF(TRIM(latitude), '')::numeric,
    NULLIF(TRIM(longitude), '')::numeric,
    NULLIF(TRIM(event_location), ''),
    NULLIF(TRIM(event_location_standardized), ''),
    CASE LOWER(TRIM(coordinates_valid))
        WHEN 'true' THEN true WHEN 'false' THEN false ELSE NULL
    END
FROM staging.location_info
WHERE location_id ~ '^\\d+$'
ON CONFLICT (location_id) DO UPDATE SET
    event_city = EXCLUDED.event_city,
    event_state = EXCLUDED.event_state,
    event_country = EXCLUDED.event_country,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude,
    event_location = EXCLUDED.event_location,
    event_location_standardized = EXCLUDED.event_location_standardized,
    coordinates_valid = EXCLUDED.coordinates_valid
"""


def sync_locations_from_staging(cur) -> int:
    cur.execute(_SYNC_LOCATIONS_SQL)
    return cur.rowcount


def count_results(cur, label: str) -> None:
    cur.execute(
        """
        SELECT
            count(*) AS total,
            count(*) FILTER (WHERE location_id IS NOT NULL) AS with_location
        FROM core.results
        """
    )
    total, with_loc = cur.fetchone()
    pct = (100.0 * with_loc / total) if total else 0.0
    print(f"{label}: {with_loc:,}/{total:,} rows with location_id ({pct:.1f}%)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory with WSDC CSV files (needs dancers_results_info.csv)",
    )
    parser.add_argument(
        "--results-only",
        action="store_true",
        help="Reload only dancers_results_info into staging (faster)",
    )
    args = parser.parse_args()

    results_csv = args.data_dir / "dancers_results_info.csv"
    location_csv = args.data_dir / "location_info.csv"
    if not results_csv.exists():
        sys.exit(f"Missing {results_csv}")
    if not location_csv.exists():
        sys.exit(f"Missing {location_csv}")

    print(f"Data directory: {args.data_dir}")

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '0'")
        conn.commit()

        if args.results_only:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE staging.dancers_results_info, staging.location_info")
                result_rows = copy_csv(conn, results_csv, "staging.dancers_results_info")
                loc_rows = copy_csv(conn, location_csv, "staging.location_info")
            conn.commit()
            print(
                f"Loaded staging: results={result_rows:,}, "
                f"locations={loc_rows:,} rows"
            )
        else:
            counts = load_staging_from_dir(conn, args.data_dir, skip_changed_roles=True)
            print(
                f"Loaded staging: "
                f"results={counts.get('dancers_results_info.csv', 0):,} rows"
            )

        with conn.cursor() as cur:
            count_results(cur, "Before")

            print("Truncating core.results ...")
            cur.execute("TRUNCATE core.results RESTART IDENTITY")

            synced = sync_locations_from_staging(cur)
            print(f"Synced core.locations from staging: {synced} row(s) touched")

            print("Promoting staging -> core.results ...")
            alias_count, orphan_count = prepare_event_resolution(conn)
            cur.execute(read_sql("promote_core_results.sql"))
            inserted = cur.rowcount
            print(
                f"Inserted {inserted:,} results; "
                f"aliases={alias_count}, orphan_events={orphan_count}"
            )

            enrich_core_known_events(conn)
            catalog_count, edition_count = rebuild_event_catalog(conn)
            cur.execute("ANALYZE core.results, core.event_editions, core.event_catalog")

            count_results(cur, "After")

            cur.execute(
                """
                SELECT
                    count(*) AS editions,
                    count(*) FILTER (WHERE location_id IS NOT NULL) AS with_location
                FROM core.event_editions
                """
            )
            editions, editions_loc = cur.fetchone()
            print(
                f"event_editions: {editions_loc:,}/{editions:,} with location_id; "
                f"event_catalog: {catalog_count:,} events, {edition_count:,} editions"
            )

        conn.commit()

    print("\nRepair complete.")


if __name__ == "__main__":
    main()

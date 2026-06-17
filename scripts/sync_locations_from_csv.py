#!/usr/bin/env python3
"""Patch core.locations coordinates from location_info.csv.

EMERGENCY ONLY — bypasses the audited preprocess → load pipeline.
Canonical path after geography changes:

    python scripts/preprocess_data.py --data-dir data
    python load.py --data-dir data

Use this script only when you cannot run a full load and need coord-only DB patches.

Usage:
    python scripts/sync_locations_from_csv.py --data-dir data
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from connection import connect  # noqa: E402
from transform.geography import normalize_geography  # noqa: E402


def load_normalized_locations(data_dir: Path) -> pd.DataFrame:
    path = data_dir / "location_info.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    return normalize_geography(df)


def sync_locations(conn, df: pd.DataFrame, dry_run: bool) -> int:
    updated = 0
    with conn.cursor() as cur:
        for row in df.itertuples(index=False):
            loc_id = int(str(row.location_id))
            lat = float(row.latitude) if str(row.latitude).strip() else None
            lon = float(row.longitude) if str(row.longitude).strip() else None
            coords_valid = str(getattr(row, "coordinates_valid", "")).lower() == "true"

            cur.execute(
                """
                SELECT latitude, longitude
                FROM core.locations
                WHERE location_id = %s
                """,
                (loc_id,),
            )
            existing = cur.fetchone()
            if existing is None:
                continue

            old_lat, old_lon = existing
            if old_lat is not None and lat is not None and abs(float(old_lat) - lat) < 1e-6:
                if old_lon is not None and lon is not None and abs(float(old_lon) - lon) < 1e-6:
                    continue

            if dry_run:
                print(
                    f"location_id={loc_id}: "
                    f"({old_lat}, {old_lon}) -> ({lat}, {lon})"
                )
            else:
                cur.execute(
                    """
                    UPDATE core.locations
                    SET latitude = %s,
                        longitude = %s,
                        coordinates_valid = %s
                    WHERE location_id = %s
                    """,
                    (lat, lon, coords_valid, loc_id),
                )
            updated += 1
    if not dry_run:
        conn.commit()
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    df = load_normalized_locations(args.data_dir)
    with connect() as conn:
        count = sync_locations(conn, df, dry_run=args.dry_run)

    action = "Would update" if args.dry_run else "Updated"
    print(f"{action} {count} location row(s)")


if __name__ == "__main__":
    main()

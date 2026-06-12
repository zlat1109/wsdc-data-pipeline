#!/usr/bin/env python3
"""HTTP cloud parser: fetch dancers and merge into existing data/ CSVs.

Uses lookup2020/find (no Selenium). Intended for incremental updates after
check_updates detects new IDs.

Usage:
    python scripts/cloud_parse.py --start-id 28367 --end-id 28367
    python scripts/cloud_parse.py --new-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from connection import connect  # noqa: E402
from parser.extract_api import build_frames  # noqa: E402
from parser.http_client import WSDCHttpClient  # noqa: E402
from wsdc_id_probe import scan_ids_above_watermark  # noqa: E402
import requests  # noqa: E402

MERGE_FILES = (
    "dancer_role_info.csv",
    "dancers_points_info.csv",
    "dancers_results_info.csv",
)


def get_db_watermark() -> int:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(dancer_id), 0) FROM core.dancers")
        return int(cur.fetchone()[0])


def resolve_id_range(args: argparse.Namespace) -> tuple[int, int]:
    if args.new_only:
        watermark = get_db_watermark()
        session = requests.Session()
        live_max = scan_ids_above_watermark(session, watermark).live_max_id
        if live_max <= watermark:
            print(f"No new IDs above watermark={watermark}")
            sys.exit(0)
        return watermark + 1, live_max
    if args.start_id is None or args.end_id is None:
        sys.exit("Provide --start-id and --end-id, or use --new-only")
    return args.start_id, args.end_id


def merge_csv(base_dir: Path, filename: str, new_df: pd.DataFrame) -> int:
    path = base_dir / filename
    if new_df.empty:
        return 0
    parsed_ids = {str(v) for v in new_df["dancer_id"].unique()}
    if path.exists():
        existing = pd.read_csv(path, dtype=str)
        existing = existing[~existing["dancer_id"].astype(str).isin(parsed_ids)]
        merged = pd.concat([existing, new_df.astype(str)], ignore_index=True)
    else:
        merged = new_df.astype(str)
    merged.to_csv(path, index=False)
    return len(new_df)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-id", type=int)
    parser.add_argument("--end-id", type=int)
    parser.add_argument("--new-only", action="store_true")
    parser.add_argument("--base-dir", type=Path, default=PROJECT_ROOT / "data")
    args = parser.parse_args()

    start_id, end_id = resolve_id_range(args)
    print(f"Parsing dancer IDs {start_id}..{end_id} into {args.base_dir}")

    client = WSDCHttpClient()
    records: list[dict] = []
    failed: list[int] = []

    for dancer_id in range(start_id, end_id + 1):
        try:
            data = client.fetch_dancer(dancer_id)
            if data:
                records.append(data)
                print(f"  OK {dancer_id}: {data.get('dancer_first')} {data.get('dancer_last')}")
            else:
                failed.append(dancer_id)
                print(f"  MISS {dancer_id}")
        except Exception as exc:  # noqa: BLE001
            failed.append(dancer_id)
            print(f"  FAIL {dancer_id}: {exc}")

    if not records:
        print("No dancers fetched — nothing to merge.")
        sys.exit(1)

    frames = build_frames(records)
    for filename in MERGE_FILES:
        count = merge_csv(args.base_dir, filename, frames[filename])
        print(f"Merged {count} rows -> {filename}")

    print(f"Done: fetched={len(records)}, failed={len(failed)}")
    if failed:
        print(f"Failed IDs: {failed}")


if __name__ == "__main__":
    main()

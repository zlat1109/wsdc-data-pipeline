#!/usr/bin/env python3
"""HTTP cloud parser: fetch dancers via lookup2020/find (no Selenium).

Production path (after check-updates gate):
    python scripts/cloud_parse.py --full
    → IDs 1..live_max_id, replace role/points/results CSVs

Manual / debug:
    python scripts/cloud_parse.py --start-id 1 --end-id 100
    python scripts/cloud_parse.py --new-only   # legacy: new IDs only (not for scheduled pipeline)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from connection import connect  # noqa: E402
from parser.extract_api import build_frames  # noqa: E402
from parser.http_client import WSDCHttpClient  # noqa: E402
from wsdc_id_probe import scan_ids_above_watermark  # noqa: E402

OUTPUT_FILES = (
    "dancer_role_info.csv",
    "dancers_points_info.csv",
    "dancers_results_info.csv",
)


def get_db_watermark() -> int:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(dancer_id), 0) FROM core.dancers")
        return int(cur.fetchone()[0])


def get_live_max_id() -> int:
    anchor = int(os.getenv("PROBE_ANCHOR_ID", "26410"))
    session = requests.Session()
    return scan_ids_above_watermark(session, anchor).live_max_id


def resolve_id_range(args: argparse.Namespace) -> tuple[int, int, bool]:
    """Return (start_id, end_id, replace_existing)."""
    if args.full:
        live_max = get_live_max_id()
        start = max(int(args.start_id or 1), 1)
        return start, live_max, True
    if args.new_only:
        watermark = get_db_watermark()
        session = requests.Session()
        live_max = scan_ids_above_watermark(session, watermark).live_max_id
        if live_max <= watermark:
            print(f"No new IDs above watermark={watermark}")
            sys.exit(0)
        return watermark + 1, live_max, False
    if args.start_id is None or args.end_id is None:
        sys.exit("Provide --start-id and --end-id, --full, or --new-only")
    return args.start_id, args.end_id, False


def write_csv(base_dir: Path, filename: str, df: pd.DataFrame, *, replace: bool) -> int:
    path = base_dir / filename
    if df.empty:
        print(f"  skip empty -> {filename}")
        return 0

    out = df.astype(str)
    if replace or not path.exists():
        out.to_csv(path, index=False)
        return len(df)

    parsed_ids = {str(v) for v in df["dancer_id"].unique()}
    existing = pd.read_csv(path, dtype=str)
    existing = existing[~existing["dancer_id"].astype(str).isin(parsed_ids)]
    merged = pd.concat([existing, out], ignore_index=True)
    merged.to_csv(path, index=False)
    return len(df)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-id", type=int)
    parser.add_argument("--end-id", type=int)
    parser.add_argument(
        "--full",
        action="store_true",
        help="Parse entire registry 1..live_max (replace CSVs; use after event gate)",
    )
    parser.add_argument(
        "--new-only",
        action="store_true",
        help="Legacy: merge only new IDs above DB watermark",
    )
    parser.add_argument("--base-dir", type=Path, default=PROJECT_ROOT / "data")
    args = parser.parse_args()

    if args.full and args.new_only:
        sys.exit("Use either --full or --new-only, not both")

    start_id, end_id, replace = resolve_id_range(args)
    total = end_id - start_id + 1
    print(
        f"Parsing dancer IDs {start_id}..{end_id} ({total} ids) "
        f"into {args.base_dir} replace={replace}",
        flush=True,
    )

    client = WSDCHttpClient()
    records: list[dict] = []
    failed: list[int] = []
    log_every = int(os.getenv("PARSE_LOG_EVERY", "500"))

    for index, dancer_id in enumerate(range(start_id, end_id + 1), start=1):
        try:
            data = client.fetch_dancer(dancer_id)
            if data:
                records.append(data)
            else:
                failed.append(dancer_id)
        except Exception as exc:  # noqa: BLE001
            failed.append(dancer_id)
            print(f"  FAIL {dancer_id}: {exc}", flush=True)

        if index % log_every == 0 or dancer_id == end_id:
            print(
                f"  progress {index}/{total} fetched={len(records)} failed={len(failed)}",
                flush=True,
            )

    if not records:
        print("No dancers fetched — nothing to write.")
        sys.exit(1)

    frames = build_frames(records)
    for filename in OUTPUT_FILES:
        count = write_csv(args.base_dir, filename, frames[filename], replace=replace)
        print(f"Wrote {count} dancer rows -> {filename}", flush=True)

    print(f"Done: fetched={len(records)}, failed={len(failed)}, replace={replace}")
    if failed:
        print(f"Failed/missing IDs ({len(failed)}): {failed[:30]}{'...' if len(failed) > 30 else ''}")


if __name__ == "__main__":
    main()

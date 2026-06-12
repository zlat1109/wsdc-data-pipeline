#!/usr/bin/env python3
"""Detect WSDC database updates by scanning for new dancer IDs above a watermark.

After weekend events, WSDC assigns new registry numbers (Newcomer/Novice first
points). This script linear-scans IDs above the last known max until
PROBE_MAX_MISSES consecutive gaps — the same logic used manually before
starting the parser.

Watermark sources (first match wins):
  1. --anchor CLI override (testing only)
  2. MAX(dancer_id) from core.dancers — текущая база после последнего парса
  3. history.parse_runs.max_dancer_id_watermark (если база ещё пустая)
  4. PROBE_ANCHOR_ID env var (default 26410)

Usage:
    python scripts/check_updates.py
    python scripts/check_updates.py --write-probe
    python scripts/check_updates.py --anchor 27135
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "db"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from connection import connect  # noqa: E402
from wsdc_id_probe import ScanResult, scan_ids_above_watermark  # noqa: E402


def get_watermark(conn, anchor_override: int | None) -> int:
    if anchor_override is not None:
        return anchor_override

    with conn.cursor() as cur:
        # Primary: max ID already loaded in our database
        cur.execute("SELECT MAX(dancer_id) FROM core.dancers")
        row = cur.fetchone()
        if row and row[0]:
            return int(row[0])

        # Fallback before first backfill
        cur.execute(
            """
            SELECT max_dancer_id_watermark
            FROM history.parse_runs
            WHERE max_dancer_id_watermark IS NOT NULL
            ORDER BY run_id DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if row and row[0]:
            return int(row[0])

    return int(os.getenv("PROBE_ANCHOR_ID", "26410"))


def record_probe(conn, result: ScanResult) -> None:
    probe_details = {
        "strategy": "new_dancer_id_scan",
        "watermark": result.watermark,
        "live_max_id": result.live_max_id,
        "approx_new_ids": max(result.live_max_id - result.watermark, 0),
        "new_dancers_sample": result.new_dancers[:10],
    }
    probe_hash = json.dumps(
        {"watermark": result.watermark, "live_max_id": result.live_max_id},
        sort_keys=True,
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO history.parse_runs (
                source, status, probe_hash,
                max_dancer_id_watermark, new_dancer_ids, probe_details,
                finished_at
            )
            VALUES ('github-actions', %s, %s, %s, %s::jsonb, %s::jsonb, %s)
            """,
            (
                "running" if result.changed else "skipped",
                probe_hash,
                result.watermark,
                json.dumps({"live_max_id": result.live_max_id, "sample": result.new_ids}),
                json.dumps(probe_details),
                datetime.now(timezone.utc),
            ),
        )
    conn.commit()


def print_report(result: ScanResult) -> None:
    print(f"watermark={result.watermark}", flush=True)
    print(f"live_max_id={result.live_max_id}", flush=True)
    approx_new = max(result.live_max_id - result.watermark, 0)
    print(f"approx_new_ids={approx_new}", flush=True)
    print(f"new_ids_sample_count={len(result.new_ids)}", flush=True)
    if result.new_ids:
        print(f"new_ids={result.new_ids}")
        print("new_dancers_sample:")
        for dancer in result.new_dancers[:10]:
            print(f"  - {dancer.get('name', dancer.get('wscid'))}")
        if len(result.new_dancers) > 10:
            print(f"  ... and {len(result.new_dancers) - 10} more")
    print("changed" if result.changed else "unchanged", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-probe",
        action="store_true",
        help="Persist probe result to history.parse_runs",
    )
    parser.add_argument(
        "--anchor",
        type=int,
        default=None,
        help="Override watermark dancer ID for this run",
    )
    args = parser.parse_args()

    session = requests.Session()

    with connect() as conn:
        watermark = get_watermark(conn, args.anchor)
        result = scan_ids_above_watermark(session, watermark)
        print_report(result)

        if args.write_probe or result.changed:
            record_probe(conn, result)


if __name__ == "__main__":
    main()

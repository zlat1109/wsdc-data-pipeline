#!/usr/bin/env python3
"""Detect when WSDC is ready for a full parse after the current upcoming weekend.

Gate logic (matches manual workflow):
  1. New dancer IDs appeared above DB watermark (Mon–Fri after weekend)
  2. Pick the newest weekend snapshot that still has events NOT in Supabase yet
     (e.g. Baltic Swing — skip J&J O'Rama / Orange Blossom once their edition is loaded)
  3. Live WSDC data from new dancers covers ALL pending upcoming events

Only when both (1) and (3) are true → print ``changed`` (triggers full-parse in CI).

Usage:
    python scripts/check_updates.py
    python scripts/check_updates.py --write-probe
    python scripts/check_updates.py --skip-event-gate   # ID probe only (testing)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from connection import connect  # noqa: E402
from event_coverage import EventCoverageResult, check_event_coverage  # noqa: E402
from parser.http_client import WSDCHttpClient  # noqa: E402
from probe_report import build_probe_report  # noqa: E402
from weekend_events import resolve_pending_snapshot  # noqa: E402
from wsdc_id_probe import ScanResult, scan_ids_above_watermark  # noqa: E402

MADRID_TZ = ZoneInfo("Europe/Madrid")


def get_watermark(conn, anchor_override: int | None) -> int:
    if anchor_override is not None:
        return anchor_override

    with conn.cursor() as cur:
        cur.execute("SELECT MAX(dancer_id) FROM core.dancers")
        row = cur.fetchone()
        if row and row[0]:
            return int(row[0])

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


def record_probe(
    conn,
    scan: ScanResult,
    coverage: EventCoverageResult | None,
    *,
    ready: bool,
) -> None:
    probe_details = {
        "strategy": "new_dancer_id_scan+event_coverage",
        "watermark": scan.watermark,
        "live_max_id": scan.live_max_id,
        "approx_new_ids": max(scan.live_max_id - scan.watermark, 0),
        "new_dancers_sample": scan.new_dancers[:10],
        "parse_ready": ready,
    }
    if coverage:
        probe_details.update({
            "pending_events": coverage.expected,
            "matched_events": coverage.matched,
            "missing_events": coverage.missing,
            "dancers_scanned_for_coverage": coverage.dancers_scanned,
            "live_event_names_sample": sorted(coverage.found_live_names)[:20],
        })
    if coverage and getattr(coverage, "already_in_db", None):
        probe_details["already_in_db_events"] = coverage.already_in_db

    probe_hash = json.dumps(
        {
            "watermark": scan.watermark,
            "live_max_id": scan.live_max_id,
            "parse_ready": ready,
            "missing_events": coverage.missing if coverage else [],
        },
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
                "running" if ready else "skipped",
                probe_hash,
                scan.live_max_id,
                json.dumps({"live_max_id": scan.live_max_id, "sample": scan.new_ids}),
                json.dumps(probe_details),
                datetime.now(timezone.utc),
            ),
        )
    conn.commit()


def get_weekly_cooldown_status(conn) -> tuple[bool, int | None, datetime | None, datetime]:
    """Return cooldown state based on successful parse runs in current Madrid week."""
    now_local = datetime.now(MADRID_TZ)
    week_start_local = (
        now_local - timedelta(days=now_local.weekday())
    ).replace(hour=0, minute=0, second=0, microsecond=0)
    next_week_start_local = week_start_local + timedelta(days=7)

    week_start_utc = week_start_local.astimezone(timezone.utc)
    next_week_start_utc = next_week_start_local.astimezone(timezone.utc)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT run_id, finished_at
            FROM history.parse_runs
            WHERE status = 'success'
              AND rows_results IS NOT NULL
              AND finished_at >= %s
            ORDER BY finished_at DESC
            LIMIT 1
            """,
            (week_start_utc,),
        )
        row = cur.fetchone()

    if not row:
        return False, None, None, next_week_start_local
    return True, int(row[0]), row[1], next_week_start_local


def print_report(
    scan: ScanResult,
    coverage: EventCoverageResult | None,
    *,
    ready: bool,
    already_in_db: list[str] | None = None,
    no_pending: bool = False,
    cooldown_active: bool = False,
    cooldown_until: str | None = None,
    last_success_run_id: int | None = None,
) -> None:
    print(f"watermark={scan.watermark}", flush=True)
    print(f"live_max_id={scan.live_max_id}", flush=True)
    approx_new = max(scan.live_max_id - scan.watermark, 0)
    print(f"approx_new_ids={approx_new}", flush=True)
    print(f"new_ids_sample_count={len(scan.new_ids)}", flush=True)

    if already_in_db:
        print(f"already_in_db_events={already_in_db}", flush=True)
    if no_pending:
        print("no_pending_events — sync current upcoming snapshot from telegram-news-bot", flush=True)
    if cooldown_active:
        print(
            f"cooldown_active_until={cooldown_until} "
            f"(last_success_run_id={last_success_run_id})",
            flush=True,
        )

    if coverage:
        print(f"pending_events={coverage.expected}", flush=True)
        for expected, matched in coverage.matched.items():
            print(f"  matched: {expected!r} -> {matched!r}", flush=True)
        if coverage.missing:
            print(f"missing_events={coverage.missing}", flush=True)
        print(f"coverage_dancers_scanned={coverage.dancers_scanned}", flush=True)

    if scan.new_ids:
        print("new_dancers_sample:")
        for dancer in scan.new_dancers[:10]:
            print(f"  - {dancer.get('name', dancer.get('wscid'))}")

    print("changed" if ready else "unchanged", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-probe", action="store_true")
    parser.add_argument("--anchor", type=int, default=None)
    parser.add_argument(
        "--skip-event-gate",
        action="store_true",
        help="Trigger on new IDs only (skip upcoming-events check)",
    )
    parser.add_argument(
        "--json-report",
        type=Path,
        default=None,
        help="Write structured probe report JSON (for Telegram notify)",
    )
    parser.add_argument(
        "--ignore-weekly-cooldown",
        action="store_true",
        help="Ignore weekly post-success cooldown (for manual override/debug)",
    )
    args = parser.parse_args()

    session = requests.Session()

    with connect() as conn:
        watermark = get_watermark(conn, args.anchor)
        scan = scan_ids_above_watermark(session, watermark)

        ids_changed = scan.live_max_id > scan.watermark
        coverage: EventCoverageResult | None = None
        ready = False
        already_in_db: list[str] = []
        no_pending = False
        snapshot_name: str | None = None
        weekend_start = weekend_end = None
        cooldown_active = False
        cooldown_until: str | None = None
        last_success_run_id: int | None = None
        last_success_finished_at: str | None = None

        if not args.ignore_weekly_cooldown:
            cooldown_active, last_success_run_id, last_success_finished_at, cooldown_until_local = (
                get_weekly_cooldown_status(conn)
            )
            cooldown_until = cooldown_until_local.isoformat()

        if cooldown_active:
            ready = False
        elif not ids_changed:
            ready = False
        elif args.skip_event_gate:
            ready = True
        else:
            snapshot, pending, already_in_db = resolve_pending_snapshot(conn)
            if not pending:
                # Nothing left to wait for: past weekends loaded or only future events ahead.
                no_pending = True
                ready = True
            else:
                snapshot_name = snapshot.source_path.name if snapshot else None
                if snapshot:
                    weekend_start = snapshot.weekend_start
                    weekend_end = snapshot.weekend_end
                    print(
                        f"weekend_snapshot={snapshot_name} "
                        f"({weekend_start}..{weekend_end})",
                        flush=True,
                    )
                http = WSDCHttpClient()
                coverage = check_event_coverage(
                    http,
                    scan.watermark + 1,
                    scan.live_max_id,
                    pending,
                )
                coverage.already_in_db = already_in_db
                ready = coverage.ready

        report = build_probe_report(
            scan,
            coverage,
            ready=ready,
            already_in_db=already_in_db,
            no_pending=no_pending,
            snapshot_name=snapshot_name,
            weekend_start=weekend_start,
            weekend_end=weekend_end,
            cooldown_active=cooldown_active,
            cooldown_until=cooldown_until,
            last_success_run_id=last_success_run_id,
            last_success_finished_at=last_success_finished_at.isoformat()
            if last_success_finished_at
            else None,
        )

        if args.json_report:
            args.json_report.write_text(
                json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        print_report(
            scan,
            coverage,
            ready=ready,
            already_in_db=already_in_db,
            no_pending=no_pending,
            cooldown_active=cooldown_active,
            cooldown_until=cooldown_until,
            last_success_run_id=last_success_run_id,
        )

        if args.write_probe or ready:
            record_probe(conn, scan, coverage, ready=ready)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Detect when WSDC is ready for a full parse after the current upcoming weekend.

Partial-readiness gate (early full-parse trigger):
  1. New dancer IDs appeared above DB watermark (Mon–Fri after weekend)
  2. Merge concluded events across all weekend snapshots (carry-over + current week)
  3. At least one pending event is visible in live WSDC data and not yet in Supabase

When (1) and (3) are true → print ``changed`` (triggers full-parse in CI).
Each trigger still runs ``cloud_parse.py --full`` (entire registry 1..live_max).

Weekly cooldown applies only when all weekend events are already loaded
(registry-only catch-up via ``gate_status=all_loaded``).

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

from check_updates_gate import (  # noqa: E402
    block_ready_if_parse_in_flight,
    evaluate_parse_ready,
)
from connection import connect  # noqa: E402
from event_coverage import EventCoverageResult, check_event_coverage  # noqa: E402
from parser.http_client import WSDCHttpClient  # noqa: E402
from probe_report import build_probe_report  # noqa: E402
from weekend_events import resolve_event_gate  # noqa: E402
from wsdc_id_probe import ScanResult, scan_ids_above_watermark  # noqa: E402
from event_db import get_db_suggestions  # noqa: E402

MADRID_TZ = ZoneInfo("Europe/Madrid")
PARSE_IN_FLIGHT_WINDOW_MINUTES = int(
    os.getenv("PARSE_IN_FLIGHT_WINDOW_MINUTES", "90")
)
STUCK_PARSE_MIN_AGE_MINUTES = int(os.getenv("STUCK_PARSE_MIN_AGE_MINUTES", "90"))
# Must exceed typical full-parse duration (~2–3h). 90m would kill live loads.
AUTO_CLOSE_STUCK_PARSE_MIN_AGE_MINUTES = int(
    os.getenv("AUTO_CLOSE_STUCK_PARSE_MIN_AGE_MINUTES", "240")
)
AUTO_CLOSE_STUCK_PARSE_RUNS = os.getenv("AUTO_CLOSE_STUCK_PARSE_RUNS", "1") == "1"


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


def get_parse_in_flight(
    conn,
    *,
    window_minutes: int | None = None,
) -> tuple[bool, int | None, int | None]:
    """Return (in_flight, run_id, age_minutes).

    Covers load.py ``running`` rows and probe triggers awaiting success
    (cloud_parse phase before load inserts its run).
    """
    window = window_minutes or PARSE_IN_FLIGHT_WINDOW_MINUTES
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window)
    now = datetime.now(timezone.utc)

    def _age(started_at) -> int | None:
        if started_at is None:
            return None
        started = started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        return int((now - started).total_seconds() // 60)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT run_id, started_at
            FROM history.parse_runs
            WHERE status = 'running'
              AND rows_results IS NULL
              AND finished_at IS NULL
              AND started_at >= %s
            ORDER BY run_id DESC
            LIMIT 1
            """,
            (cutoff,),
        )
        row = cur.fetchone()
        if row:
            return True, int(row[0]), _age(row[1])

        cur.execute(
            """
            SELECT pr.run_id, pr.started_at
            FROM history.parse_runs pr
            WHERE pr.status = 'running'
              AND pr.finished_at IS NOT NULL
              AND pr.probe_details->>'parse_ready' = 'true'
              AND pr.started_at >= %s
              AND NOT EXISTS (
                  SELECT 1
                  FROM history.parse_runs s
                  WHERE s.status = 'success'
                    AND s.rows_results IS NOT NULL
                    AND s.finished_at > pr.finished_at
              )
            ORDER BY pr.run_id DESC
            LIMIT 1
            """,
            (cutoff,),
        )
        row = cur.fetchone()
    if not row:
        return False, None, None
    return True, int(row[0]), _age(row[1])


def record_probe(
    conn,
    scan: ScanResult,
    coverage: EventCoverageResult | None,
    *,
    ready: bool,
    gate_status: str | None = None,
    ready_reason: str | None = None,
    trigger_events: list[str] | None = None,
    pending: list[str] | None = None,
    already_in_db: list[str] | None = None,
) -> None:
    pending = list(pending or [])
    already_in_db = list(already_in_db or [])
    probe_details = {
        "strategy": "new_dancer_id_scan+event_coverage",
        "watermark": scan.watermark,
        "live_max_id": scan.live_max_id,
        "approx_new_ids": max(scan.live_max_id - scan.watermark, 0),
        "new_dancers_sample": scan.new_dancers[:10],
        "parse_ready": ready,
        "gate_status": gate_status,
        "ready_reason": ready_reason,
        "trigger_events": list(trigger_events or []),
        "pending_events": list(coverage.expected) if coverage else pending,
        "already_in_db_events": (
            list(getattr(coverage, "already_in_db", None) or already_in_db)
            if coverage
            else already_in_db
        ),
    }
    if coverage:
        probe_details.update({
            "matched_events": coverage.matched,
            "missing_events": coverage.missing,
            "dancers_scanned_for_coverage": coverage.dancers_scanned,
            "live_event_names_sample": sorted(coverage.found_live_names)[:20],
        })

    probe_hash = json.dumps(
        {
            "watermark": scan.watermark,
            "live_max_id": scan.live_max_id,
            "parse_ready": ready,
            "missing_events": coverage.missing if coverage else [],
            "ready_reason": ready_reason,
            "trigger_events": list(trigger_events or []),
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
    pending: list[str] | None = None,
    already_in_db: list[str] | None = None,
    gate_status: str | None = None,
    ready_reason: str | None = None,
    trigger_events: list[str] | None = None,
    parse_in_flight: bool = False,
    parse_in_flight_run_id: int | None = None,
    parse_in_flight_age_minutes: int | None = None,
    zombie_parse_close: dict | None = None,
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
    if gate_status:
        print(f"gate_status={gate_status}", flush=True)
    if gate_status == "no_concluded_events":
        print(
            "no_concluded_events — quiet weekend or only future events in snapshots",
            flush=True,
        )
    if trigger_events:
        print(f"trigger_events={trigger_events}", flush=True)
    if parse_in_flight:
        print(
            f"parse_in_flight=true (run_id={parse_in_flight_run_id}"
            + (
                f", age_minutes={parse_in_flight_age_minutes}"
                if parse_in_flight_age_minutes is not None
                else ""
            )
            + ")",
            flush=True,
        )
    if zombie_parse_close and zombie_parse_close.get("closed_count"):
        print(
            f"zombie_parse_closed={zombie_parse_close['closed_count']}",
            flush=True,
        )
    if ready_reason:
        print(f"ready_reason={ready_reason}", flush=True)
    if cooldown_active:
        print(
            f"cooldown_active_until={cooldown_until} "
            f"(last_success_run_id={last_success_run_id})",
            flush=True,
        )

    pending_events = list(coverage.expected) if coverage else list(pending or [])
    if pending_events:
        print(f"pending_events={pending_events}", flush=True)
    if coverage:
        for expected, matched in coverage.matched.items():
            print(f"  matched: {expected!r} -> {matched!r}", flush=True)
        if coverage.missing:
            print(f"missing_events={coverage.missing}", flush=True)
        print(f"coverage_dancers_scanned={coverage.dancers_scanned}", flush=True)
        suggestions = get_db_suggestions()
        if suggestions:
            print(f"db_name_suggestions={list(suggestions.keys())}", flush=True)

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
        ready_reason = "no_new_ids"
        trigger_events: list[str] = []
        gate_status = "no_concluded_events"
        pending: list[str] = []
        already_in_db: list[str] = []
        snapshot_name: str | None = None
        weekend_start = weekend_end = None
        cooldown_active = False
        cooldown_until: str | None = None
        last_success_run_id: int | None = None
        last_success_finished_at: str | None = None
        parse_in_flight = False
        parse_in_flight_run_id: int | None = None
        parse_in_flight_age_minutes: int | None = None
        zombie_parse_close: dict | None = None

        if AUTO_CLOSE_STUCK_PARSE_RUNS:
            from close_parse_runs import close_stuck_running_parse_runs

            zombie_parse_close = close_stuck_running_parse_runs(
                conn,
                min_age_minutes=AUTO_CLOSE_STUCK_PARSE_MIN_AGE_MINUTES,
                dry_run=False,
            )
            if zombie_parse_close.get("closed_count"):
                print(
                    f"auto-closed stuck parse_runs: "
                    f"{zombie_parse_close['closed_count']} "
                    f"(age>={AUTO_CLOSE_STUCK_PARSE_MIN_AGE_MINUTES}m)",
                    flush=True,
                )

        parse_in_flight, parse_in_flight_run_id, parse_in_flight_age_minutes = (
            get_parse_in_flight(conn)
        )

        if not args.ignore_weekly_cooldown:
            cooldown_active, last_success_run_id, last_success_finished_at, cooldown_until_local = (
                get_weekly_cooldown_status(conn)
            )
            cooldown_until = cooldown_until_local.isoformat()

        if args.skip_event_gate:
            ready, ready_reason, trigger_events = evaluate_parse_ready(
                ids_changed=ids_changed,
                skip_event_gate=True,
                cooldown_active=cooldown_active,
                ignore_cooldown=args.ignore_weekly_cooldown,
                gate_status="pending",
                coverage=None,
            )
        else:
            # Always resolve gate for reporting — even when watermark caught up
            # after a partial parse (remaining pending events still matter).
            snapshot, pending, already_in_db, gate_status = resolve_event_gate(conn)
            if snapshot:
                snapshot_name = snapshot.source_path.name
                weekend_start = snapshot.weekend_start
                weekend_end = snapshot.weekend_end
                print(
                    f"weekend_snapshot={snapshot_name} "
                    f"({weekend_start}..{weekend_end})",
                    flush=True,
                )
            if ids_changed and gate_status == "pending":
                http = WSDCHttpClient()
                coverage = check_event_coverage(
                    http,
                    scan.watermark + 1,
                    scan.live_max_id,
                    pending,
                )
                coverage.already_in_db = already_in_db
            ready, ready_reason, trigger_events = evaluate_parse_ready(
                ids_changed=ids_changed,
                skip_event_gate=False,
                cooldown_active=cooldown_active,
                ignore_cooldown=args.ignore_weekly_cooldown,
                gate_status=gate_status,
                coverage=coverage,
                pending=pending,
                already_in_db=already_in_db,
            )

        ready, ready_reason = block_ready_if_parse_in_flight(
            ready,
            ready_reason,
            parse_in_flight=parse_in_flight,
        )

        report = build_probe_report(
            scan,
            coverage,
            ready=ready,
            pending=pending,
            already_in_db=already_in_db,
            gate_status=gate_status,
            ready_reason=ready_reason,
            trigger_events=trigger_events,
            parse_in_flight=parse_in_flight,
            parse_in_flight_run_id=parse_in_flight_run_id,
            parse_in_flight_age_minutes=parse_in_flight_age_minutes,
            zombie_parse_close=zombie_parse_close,
            snapshot_name=snapshot_name,
            weekend_start=weekend_start,
            weekend_end=weekend_end,
            cooldown_active=cooldown_active,
            cooldown_until=cooldown_until,
            last_success_run_id=last_success_run_id,
            last_success_finished_at=last_success_finished_at.isoformat()
            if last_success_finished_at
            else None,
            db_name_suggestions=get_db_suggestions(),
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
            pending=pending,
            already_in_db=already_in_db,
            gate_status=gate_status,
            ready_reason=ready_reason,
            trigger_events=trigger_events,
            parse_in_flight=parse_in_flight,
            parse_in_flight_run_id=parse_in_flight_run_id,
            parse_in_flight_age_minutes=parse_in_flight_age_minutes,
            zombie_parse_close=zombie_parse_close,
            cooldown_active=cooldown_active,
            cooldown_until=cooldown_until,
            last_success_run_id=last_success_run_id,
        )

        if args.write_probe or ready:
            record_probe(
                conn,
                scan,
                coverage,
                ready=ready,
                gate_status=gate_status,
                ready_reason=ready_reason,
                trigger_events=trigger_events,
                pending=pending,
                already_in_db=already_in_db,
            )


if __name__ == "__main__":
    main()

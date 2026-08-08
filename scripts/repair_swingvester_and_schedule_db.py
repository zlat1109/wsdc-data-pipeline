#!/usr/bin/env python3
"""Apply SwingVester Wels remap + reload empty events_list_current into Supabase.

PR #121 fixed git CSVs / knowledge overrides, but live DB still had:
  - core.results / editions / catalog for event_id 289 on Brno (266)
  - empty core.events_list_current → export.scheduled_events = 0 rows
  - edition_calendar_dates ghost (289, 2026, 12) start-only NYE row

Usage:
    python scripts/repair_swingvester_and_schedule_db.py --dry-run
    python scripts/repair_swingvester_and_schedule_db.py --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.dry_run == args.apply:
        print("Specify exactly one of --dry-run or --apply")
        return 2

    from connection import connect
    from sync_events_list import load_to_supabase
    from transform.events_list_catalog import load_catalog

    current_path = PROJECT_ROOT / "data" / "events_list" / "current.json"
    doc = json.loads(current_path.read_text(encoding="utf-8"))
    events = doc.get("events") or []
    if not events:
        print("No events in data/events_list/current.json")
        return 1

    loc = pd.read_csv(PROJECT_ROOT / "data" / "location_info.csv", dtype=str)
    valid = set(loc["location_id"].astype(str).str.strip())
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT location_id::text FROM core.locations")
            valid |= {r[0] for r in cur.fetchall()}
            cur.execute("SELECT count(*) FROM core.events_list_current")
            list_n = cur.fetchone()[0]
            cur.execute(
                "SELECT location_id, count(*) FROM core.results "
                "WHERE event_id = 289 GROUP BY 1"
            )
            lids = cur.fetchall()
            cur.execute(
                "SELECT typical_location FROM core.event_catalog WHERE event_id = 289"
            )
            cat = cur.fetchone()
            cur.execute(
                "SELECT event_year, event_month, planned_start_date, planned_end_date "
                "FROM core.edition_calendar_dates WHERE event_id = 289 ORDER BY 1, 2"
            )
            cal = cur.fetchall()

    print(f"events_list_current rows: {list_n}")
    print(f"SwingVester results lids: {lids}")
    print(f"SwingVester catalog: {cat}")
    print(f"SwingVester calendar rows: {cal}")
    if args.dry_run:
        print("dry-run only — no writes")
        return 0

    cleared = 0
    for ev in events:
        lid = str(ev.get("location_id") or "").strip()
        if lid and lid not in valid:
            ev["location_id"] = None
            ev["location_source"] = None
            cleared += 1
    print(f"cleared invalid schedule location_ids: {cleared}")

    catalog = load_catalog()
    run_id, current_count, _, _ = load_to_supabase(
        events, [], [], len(events), "local", catalog
    )
    print(f"reloaded schedule run_id={run_id} current_events={current_count}")

    now = datetime.now(timezone.utc)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE core.results SET location_id = 197 "
                "WHERE event_id = 289 AND location_id IS DISTINCT FROM 197"
            )
            print(f"results → 197: {cur.rowcount}")
            cur.execute(
                "UPDATE core.event_editions SET location_id = 197 "
                "WHERE event_id = 289 AND location_id IS DISTINCT FROM 197"
            )
            print(f"editions → 197: {cur.rowcount}")
            cur.execute(
                """
                UPDATE core.event_catalog
                SET typical_city = 'Wels', typical_state = NULL,
                    typical_country = 'Austria', typical_location = 'Wels, Austria'
                WHERE event_id = 289
                """
            )
            print(f"catalog → Wels: {cur.rowcount}")
            cur.execute(
                "DELETE FROM core.edition_calendar_dates "
                "WHERE event_id = 289 AND event_year = 2026 AND event_month = 12"
            )
            print(f"deleted ghost 2026/12: {cur.rowcount}")
            cur.execute(
                """
                INSERT INTO core.edition_calendar_dates (
                    event_id, event_year, event_month,
                    planned_start_date, planned_end_date,
                    calendar_status, date_source, source_fingerprint,
                    calendar_title, url, match_via, scraped_at, updated_at
                ) VALUES (
                    289, 2027, 1,
                    DATE '2026-12-30', DATE '2027-01-04',
                    'scheduled', 'wsdc_calendar', 'd8a575f459c377efad9e5a4b',
                    'SwingVester', 'https://www.swingvester.com/', 'url', %s, %s
                )
                ON CONFLICT (event_id, event_year, event_month) DO UPDATE SET
                    planned_start_date = EXCLUDED.planned_start_date,
                    planned_end_date = EXCLUDED.planned_end_date,
                    calendar_status = EXCLUDED.calendar_status,
                    date_source = EXCLUDED.date_source,
                    source_fingerprint = EXCLUDED.source_fingerprint,
                    calendar_title = EXCLUDED.calendar_title,
                    url = EXCLUDED.url,
                    match_via = EXCLUDED.match_via,
                    scraped_at = EXCLUDED.scraped_at,
                    updated_at = EXCLUDED.updated_at
                """,
                (now, now),
            )
            print("upserted calendar 2027/1")
            cur.execute("SELECT count(*) FROM export.scheduled_events")
            print(f"export.scheduled_events: {cur.fetchone()[0]}")
        conn.commit()
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

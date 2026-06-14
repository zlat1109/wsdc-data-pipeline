#!/usr/bin/env python3
"""Scrape WSDC Events List, diff vs previous run, load Supabase, notify Telegram.

Usage:
    python scripts/sync_events_list.py
    python scripts/sync_events_list.py --dry-run
    python scripts/sync_events_list.py --skip-db --skip-telegram
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from parser.events_list_scraper import scrape_events_list  # noqa: E402
from refresh_events_list_current import refresh_events_list_current  # noqa: E402
from transform.events_list_catalog import load_catalog  # noqa: E402
from transform.events_list_mapping import CatalogEvent, analyze_mapping  # noqa: E402
from transform.events_list_normalize import normalize_events  # noqa: E402

DATA_DIR = PROJECT_ROOT / "data" / "events_list"
MAPPING_DIR = DATA_DIR / "mapping"
CURRENT_PATH = DATA_DIR / "current.json"
CSV_PATH = DATA_DIR / "events_list.csv"
CHANGELOG_DIR = DATA_DIR / "changelog"


def load_previous_current() -> dict[str, dict[str, Any]]:
    if not CURRENT_PATH.exists():
        return {}
    data = json.loads(CURRENT_PATH.read_text(encoding="utf-8"))
    events = data.get("events") or []
    return {e["source_fingerprint"]: e for e in events}


def compute_diff(
    previous: dict[str, dict[str, Any]],
    current: dict[str, dict[str, Any]],
) -> tuple[list[dict], list[dict], int]:
    prev_keys = set(previous)
    curr_keys = set(current)
    added_keys = curr_keys - prev_keys
    removed_keys = prev_keys - curr_keys
    unchanged = len(curr_keys & prev_keys)

    added = [current[k] for k in sorted(added_keys, key=lambda k: current[k].get("start_date", ""))]
    removed = [previous[k] for k in sorted(removed_keys, key=lambda k: previous[k].get("start_date", ""))]
    return added, removed, unchanged


def save_artifacts(
    events: list[dict[str, Any]],
    added: list[dict],
    removed: list[dict],
    unchanged: int,
    source: str,
    *,
    parse_errors: int = 0,
) -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CHANGELOG_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")

    report: dict[str, Any] = {
        "scraped_at": now.isoformat(),
        "source": source,
        "summary": {
            "total": len(events),
            "added": len(added),
            "removed": len(removed),
            "unchanged": unchanged,
            "parse_errors": parse_errors,
        },
        "added": added,
        "removed": removed,
    }

    current_doc = {
        "scraped_at": now.isoformat(),
        "source": source,
        "events": events,
    }
    CURRENT_PATH.write_text(json.dumps(current_doc, ensure_ascii=False, indent=2), encoding="utf-8")

    changelog_path = CHANGELOG_DIR / f"run_{stamp}.json"
    changelog_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (CHANGELOG_DIR / "latest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    fieldnames = [
        "source_fingerprint",
        "event_name",
        "original_date",
        "start_date",
        "end_date",
        "results_year",
        "results_month",
        "location_raw",
        "country",
        "country_flag",
        "url",
        "status_event",
        "confirmed",
        "canceled",
        "on_hiatus",
        "is_active",
    ]
    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in sorted(events, key=lambda r: (r.get("start_date", ""), r.get("event_name", ""))):
            writer.writerow(row)

    report["paths"] = {
        "current": str(CURRENT_PATH),
        "csv": str(CSV_PATH),
        "changelog": str(changelog_path),
    }
    return report


def load_to_supabase(
    events: list[dict[str, Any]],
    added: list[dict],
    removed: list[dict],
    unchanged: int,
    source: str,
    catalog: list[CatalogEvent],
) -> tuple[int, int]:
    from connection import connect

    now = datetime.now(timezone.utc)
    current_fps = {e["source_fingerprint"] for e in events}

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO history.events_list_runs
                    (scraped_at, source, total_events, added_count, removed_count, unchanged_count)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING run_id
                """,
                (now, source, len(events), len(added), len(removed), unchanged),
            )
            run_id = cur.fetchone()[0]

            for ev in events:
                cur.execute(
                    """
                    INSERT INTO core.scheduled_events (
                        source_fingerprint, event_name, original_date,
                        start_date, end_date, results_year, results_month,
                        location_raw, country, country_flag, url,
                        status_event, confirmed, canceled, on_hiatus, is_active,
                        first_seen_at, last_seen_at, last_run_id
                    ) VALUES (
                        %(source_fingerprint)s, %(event_name)s, %(original_date)s,
                        %(start_date)s, %(end_date)s, %(results_year)s, %(results_month)s,
                        %(location_raw)s, %(country)s, %(country_flag)s, %(url)s,
                        %(status_event)s, %(confirmed)s, %(canceled)s, %(on_hiatus)s, %(is_active)s,
                        %(now)s, %(now)s, %(run_id)s
                    )
                    ON CONFLICT (source_fingerprint) DO UPDATE SET
                        event_name = EXCLUDED.event_name,
                        original_date = EXCLUDED.original_date,
                        start_date = EXCLUDED.start_date,
                        end_date = EXCLUDED.end_date,
                        results_year = EXCLUDED.results_year,
                        results_month = EXCLUDED.results_month,
                        location_raw = EXCLUDED.location_raw,
                        country = EXCLUDED.country,
                        country_flag = EXCLUDED.country_flag,
                        url = EXCLUDED.url,
                        status_event = EXCLUDED.status_event,
                        confirmed = EXCLUDED.confirmed,
                        canceled = EXCLUDED.canceled,
                        on_hiatus = EXCLUDED.on_hiatus,
                        is_active = EXCLUDED.is_active,
                        last_seen_at = EXCLUDED.last_seen_at,
                        last_run_id = EXCLUDED.last_run_id
                    """,
                    {**ev, "now": now, "run_id": run_id},
                )

            if current_fps:
                cur.execute(
                    """
                    UPDATE core.scheduled_events
                    SET is_active = false, last_seen_at = %s, last_run_id = %s
                    WHERE is_active = true
                      AND NOT (source_fingerprint = ANY(%s))
                    """,
                    (now, run_id, list(current_fps)),
                )

            for ev in added:
                cur.execute(
                    """
                    INSERT INTO history.events_list_changes
                        (run_id, change_type, source_fingerprint, event_name,
                         start_date, end_date, location_raw, url, snapshot)
                    VALUES (%s, 'added', %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        run_id,
                        ev["source_fingerprint"],
                        ev["event_name"],
                        ev["start_date"],
                        ev["end_date"],
                        ev.get("location_raw"),
                        ev.get("url"),
                        json.dumps(ev, ensure_ascii=False),
                    ),
                )

            for ev in removed:
                cur.execute(
                    """
                    INSERT INTO history.events_list_changes
                        (run_id, change_type, source_fingerprint, event_name,
                         start_date, end_date, location_raw, url, snapshot)
                    VALUES (%s, 'removed', %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        run_id,
                        ev["source_fingerprint"],
                        ev["event_name"],
                        ev.get("start_date"),
                        ev.get("end_date"),
                        ev.get("location_raw"),
                        ev.get("url"),
                        json.dumps(ev, ensure_ascii=False),
                    ),
                )

            current_count = refresh_events_list_current(
                conn, events, run_id, catalog=catalog
            )

            from build_event_catalog import rebuild_event_catalog

            rebuild_event_catalog(conn)

        conn.commit()
    return run_id, current_count


def run_mapping_analysis(
    events: list[dict[str, Any]],
    catalog: list[CatalogEvent] | None = None,
) -> dict[str, Any]:
    """Compare schedule to points catalog; save mapping/latest.json."""
    if catalog is None:
        catalog = load_catalog()
    report = analyze_mapping(events, catalog)
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["catalog_events"] = len(catalog)

    MAPPING_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = MAPPING_DIR / f"mapping_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (MAPPING_DIR / "latest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def print_mapping_summary(report: dict[str, Any]) -> None:
    s = report.get("summary") or {}
    print("\n=== Catalog mapping ===")
    print(f"Confirmed: {s.get('confirmed', 0)}  Review: {s.get('review', 0)}  New: {s.get('new_unmapped', 0)}")
    print(f"Location drifts: {s.get('location_drifts', 0)}")


def print_summary(report: dict[str, Any]) -> None:
    s = report["summary"]
    print("\n=== WSDC Events List sync ===")
    print(f"Total on site: {s['total']}")
    print(f"Added: {s['added']}  Removed: {s['removed']}  Unchanged: {s['unchanged']}")
    if report.get("added"):
        print("\nAdded (sample):")
        for ev in report["added"][:8]:
            print(f"  + {ev['event_name']} ({ev.get('start_date')} — {ev.get('location_raw', '')[:40]})")
    if report.get("removed"):
        print("\nRemoved (sample):")
        for ev in report["removed"][:8]:
            print(f"  - {ev['event_name']} ({ev.get('start_date')})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Scrape + diff only, no DB/Telegram")
    parser.add_argument("--skip-db", action="store_true")
    parser.add_argument("--skip-telegram", action="store_true")
    parser.add_argument("--source", default="local", choices=["local", "github-actions"])
    args = parser.parse_args()

    print("Scraping worldsdc.com/events/ ...")
    scrape_result = scrape_events_list()
    parse_error_count = len(scrape_result.parse_errors)
    if parse_error_count:
        print(f"Parse errors: {parse_error_count}", file=sys.stderr)
    events = normalize_events(scrape_result.events)
    current_map = {e["source_fingerprint"]: e for e in events}

    previous = load_previous_current()
    added, removed, unchanged = compute_diff(previous, current_map)

    report = save_artifacts(
        events, added, removed, unchanged, args.source, parse_errors=parse_error_count
    )
    print_summary(report)

    catalog: list[CatalogEvent] | None = None
    try:
        catalog = load_catalog()
        mapping_report = run_mapping_analysis(events, catalog=catalog)
        print_mapping_summary(mapping_report)
        report["mapping_summary"] = mapping_report.get("summary")
    except Exception as exc:
        print(f"\nMapping analysis skipped: {exc}", file=sys.stderr)

    if not args.dry_run and not args.skip_db:
        try:
            if catalog is None:
                catalog = load_catalog()
            run_id, current_count = load_to_supabase(
                events, added, removed, unchanged, args.source, catalog
            )
            print(f"\nSupabase run_id={run_id}  current_events={current_count}")
            report["run_id"] = run_id
            report["current_events"] = current_count
        except Exception as exc:
            print(f"\nDB load failed: {exc}", file=sys.stderr)
            if args.source == "github-actions":
                raise

    if not args.dry_run and not args.skip_telegram:
        import subprocess

        subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "telegram_notify.py"), "events-list"],
            cwd=PROJECT_ROOT,
            check=False,
        )


if __name__ == "__main__":
    main()

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
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

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
            "active": sum(1 for e in events if e.get("is_active", True)),
            "inactive": sum(1 for e in events if not e.get("is_active", True)),
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
        "location_id",
        "location_source",
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
    *,
    location_df: Any = None,
    location_ids_touched: set[str] | None = None,
) -> tuple[int, int, Any, list[dict[str, Any]]]:
    from connection import connect
    from transform.geography.schedule_locations import (
        apply_location_id_remaps,
        upsert_locations_to_db,
    )

    now = datetime.now(timezone.utc)
    current_fps = {e["source_fingerprint"] for e in events}

    with connect() as conn:
        with conn.cursor() as cur:
            if location_df is not None and location_ids_touched:
                n_loc, remaps = upsert_locations_to_db(
                    cur, location_df, location_ids_touched
                )
                if remaps:
                    events, location_df = apply_location_id_remaps(
                        events, location_df, remaps
                    )
                    print(f"Location id remaps: {remaps}")
                print(f"Locations upserted: {n_loc}")

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
                        status_event, location_id, location_source,
                        confirmed, canceled, on_hiatus, is_active,
                        first_seen_at, last_seen_at, last_run_id
                    ) VALUES (
                        %(source_fingerprint)s, %(event_name)s, %(original_date)s,
                        %(start_date)s, %(end_date)s, %(results_year)s, %(results_month)s,
                        %(location_raw)s, %(country)s, %(country_flag)s, %(url)s,
                        %(status_event)s, %(location_id)s, %(location_source)s,
                        %(confirmed)s, %(canceled)s, %(on_hiatus)s, %(is_active)s,
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
                        location_id = COALESCE(
                            core.scheduled_events.location_id, EXCLUDED.location_id
                        ),
                        location_source = CASE
                            WHEN core.scheduled_events.location_id IS NULL
                            THEN EXCLUDED.location_source
                            ELSE core.scheduled_events.location_source
                        END,
                        confirmed = EXCLUDED.confirmed,
                        canceled = EXCLUDED.canceled,
                        on_hiatus = EXCLUDED.on_hiatus,
                        is_active = EXCLUDED.is_active,
                        last_seen_at = EXCLUDED.last_seen_at,
                        last_run_id = EXCLUDED.last_run_id
                    """,
                    {
                        **ev,
                        "now": now,
                        "run_id": run_id,
                        "location_id": ev.get("location_id"),
                        "location_source": ev.get("location_source") or None,
                    },
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

            # Same Tuesday job: calendar day-precision → durable store, then rebuild.
            try:
                from sync_events_calendar import sync_events_calendar

                cal = sync_events_calendar(conn=conn, rebuild_catalog=False)
                print(
                    f"Calendar sync: {cal.get('event_count', 0)} rows, "
                    f"upserted={cal.get('upserted', 0)}"
                )
            except Exception as exc:
                print(f"Calendar sync failed (continuing list rebuild): {exc}", file=sys.stderr)

            from build_event_catalog import rebuild_event_catalog

            rebuild_event_catalog(conn)

        conn.commit()
    return run_id, current_count, location_df, events


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
    print(
        f"Confirmed: {s.get('confirmed', 0)}  Suggested: {s.get('suggested', 0)}  "
        f"Review: {s.get('review', 0)}  New: {s.get('new_unmapped', 0)}"
    )
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


def _carry_forward_location_ids(
    events: list[dict[str, Any]],
    previous: dict[str, dict[str, Any]],
) -> None:
    """Keep previously resolved schedule location_id across scrapes."""
    for ev in events:
        if ev.get("location_id"):
            continue
        prev = previous.get(ev["source_fingerprint"]) or {}
        lid = prev.get("location_id")
        if lid is None or str(lid).strip() == "":
            continue
        ev["location_id"] = lid
        ev["location_source"] = prev.get("location_source") or "location_info"


def _assign_trial_geo(
    events: list[dict[str, Any]],
    *,
    allow_geocode: bool = True,
    id_floor: int = 0,
    write_csv: bool = False,
) -> tuple[list[dict[str, Any]], Any, list[dict[str, Any]], set[str]]:
    """Resolve Trial Event geo into location_info + event location_id fields.

    By default does **not** write location_info.csv — caller should persist after
    a successful DB commit (or pass write_csv=True for offline --skip-db runs).
    """
    import pandas as pd
    from transform.geography.schedule_locations import assign_schedule_locations

    loc_path = PROJECT_ROOT / "data" / "location_info.csv"
    location_df = (
        pd.read_csv(loc_path, dtype=str)
        if loc_path.exists()
        else pd.DataFrame()
    )
    before_ids = set(
        location_df["location_id"].astype(str).str.strip()
        if not location_df.empty and "location_id" in location_df.columns
        else []
    )
    before_coords = {}
    if not location_df.empty:
        for _, row in location_df.iterrows():
            lid = str(row.get("location_id") or "").strip()
            before_coords[lid] = (
                str(row.get("latitude") or ""),
                str(row.get("longitude") or ""),
            )

    events, location_df, review = assign_schedule_locations(
        events,
        location_df,
        allow_geocode=allow_geocode,
        id_floor=id_floor,
    )

    touched: set[str] = set()
    if not location_df.empty and "location_id" in location_df.columns:
        for _, row in location_df.iterrows():
            lid = str(row.get("location_id") or "").strip()
            if not lid:
                continue
            if lid not in before_ids:
                touched.add(lid)
                continue
            coords = (str(row.get("latitude") or ""), str(row.get("longitude") or ""))
            if before_coords.get(lid) != coords:
                touched.add(lid)

    if write_csv and (touched or len(location_df) != len(before_ids)):
        location_df.to_csv(loc_path, index=False)
        print(f"Updated location_info.csv (touched_ids={len(touched)})")

    return events, location_df, review, touched


def _fetch_db_location_id_floor() -> int:
    try:
        from connection import connect
        from transform.geography.schedule_locations import db_max_location_id

        with connect() as conn:
            with conn.cursor() as cur:
                return db_max_location_id(cur)
    except Exception as exc:  # noqa: BLE001
        print(f"DB location_id floor unavailable ({exc}); using CSV max only", flush=True)
        return 0


def _persist_location_info_csv(location_df: Any) -> None:
    if location_df is None:
        return
    loc_path = PROJECT_ROOT / "data" / "location_info.csv"
    location_df.to_csv(loc_path, index=False)
    print(f"Wrote location_info.csv ({len(location_df)} rows)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Scrape + diff only, no DB/Telegram")
    parser.add_argument("--skip-db", action="store_true")
    parser.add_argument("--skip-telegram", action="store_true")
    parser.add_argument("--skip-geocode", action="store_true", help="Reuse locations only; no Google")
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
    _carry_forward_location_ids(events, previous)
    added, removed, unchanged = compute_diff(previous, current_map)

    geo_review: list[dict[str, Any]] = []
    location_df = None
    location_ids_touched: set[str] = set()
    try:
        id_floor = 0
        if not args.dry_run and not args.skip_db:
            id_floor = _fetch_db_location_id_floor()
            if id_floor:
                print(f"DB location_id floor: {id_floor}")
        events, location_df, geo_review, location_ids_touched = _assign_trial_geo(
            events,
            allow_geocode=not args.skip_geocode,
            id_floor=id_floor,
            write_csv=bool(args.skip_db or args.dry_run),
        )
        trial_with_geo = sum(
            1
            for e in events
            if "trial" in str(e.get("status_event") or "").lower() and e.get("location_id")
        )
        print(f"Trial geo: {trial_with_geo} with location_id, review={len(geo_review)}")
    except Exception as exc:
        print(f"Trial geo assignment failed (continuing): {exc}", file=sys.stderr)

    report = save_artifacts(
        events, added, removed, unchanged, args.source, parse_errors=parse_error_count
    )
    report["summary"]["geo_review_count"] = len(geo_review)
    report["geo_review"] = geo_review
    (CHANGELOG_DIR / "latest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print_summary(report)

    catalog: list[CatalogEvent] | None = None
    try:
        catalog = load_catalog()
        mapping_report = run_mapping_analysis(events, catalog=catalog)
        print_mapping_summary(mapping_report)
        report["mapping_summary"] = mapping_report.get("summary")
        (CHANGELOG_DIR / "latest.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as exc:
        print(f"\nMapping analysis skipped: {exc}", file=sys.stderr)

    if not args.dry_run and not args.skip_db:
        try:
            if catalog is None:
                catalog = load_catalog()
            run_id, current_count, location_df, events = load_to_supabase(
                events,
                added,
                removed,
                unchanged,
                args.source,
                catalog,
                location_df=location_df,
                location_ids_touched=location_ids_touched,
            )
            # Persist CSV only after successful DB commit.
            if location_ids_touched:
                _persist_location_info_csv(location_df)
            # Refresh local artifacts with remapped location_ids.
            report = save_artifacts(
                events,
                added,
                removed,
                unchanged,
                args.source,
                parse_errors=parse_error_count,
            )
            report["summary"]["geo_review_count"] = len(geo_review)
            report["geo_review"] = geo_review
            report["run_id"] = run_id
            report["current_events"] = current_count
            (CHANGELOG_DIR / "latest.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"\nSupabase run_id={run_id}  current_events={current_count}")
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

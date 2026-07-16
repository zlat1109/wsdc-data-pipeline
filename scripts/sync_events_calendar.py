#!/usr/bin/env python3
"""Scrape WSDC Events Calendar, save artifacts, upsert durable edition dates.

Usage:
    python scripts/sync_events_calendar.py
    python scripts/sync_events_calendar.py --min-start 2024-01-01
    python scripts/sync_events_calendar.py --all-years
    python scripts/sync_events_calendar.py --skip-db
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from parser.events_calendar_scraper import CALENDAR_URL, scrape_events_calendar  # noqa: E402
from transform.events_calendar_match import match_calendar_to_editions  # noqa: E402
from transform.events_calendar_normalize import normalize_calendar_events  # noqa: E402

DATA_DIR = PROJECT_ROOT / "data" / "events_calendar"
CURRENT_PATH = DATA_DIR / "current.json"
CSV_PATH = DATA_DIR / "events_calendar.csv"
MATCHED_CSV_PATH = DATA_DIR / "edition_date_matches.csv"
REPORT_PATH = DATA_DIR / "match_report.json"

CSV_FIELDS = [
    "event_name",
    "calendar_title",
    "catalog_name",
    "start_date",
    "end_date",
    "url",
    "results_year",
    "results_month",
    "edition_ym_candidates",
    "date_precision",
    "date_source",
    "flags",
    "source_fingerprint",
]


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            out = dict(row)
            if isinstance(out.get("flags"), list):
                out["flags"] = "|".join(out["flags"])
            if isinstance(out.get("edition_ym_candidates"), list):
                out["edition_ym_candidates"] = "|".join(out["edition_ym_candidates"])
            if isinstance(out.get("status_tags"), list):
                out["status_tags"] = "|".join(out["status_tags"])
            writer.writerow({k: out.get(k, "") for k in fields})


def _load_match_frames_from_csv() -> tuple[pd.DataFrame, pd.DataFrame]:
    editions_path = PROJECT_ROOT / "data" / "event_editions.csv"
    catalog_path = PROJECT_ROOT / "data" / "event_catalog.csv"
    editions = (
        pd.read_csv(editions_path, dtype=str) if editions_path.exists() else pd.DataFrame()
    )
    catalog = pd.read_csv(catalog_path, dtype=str) if catalog_path.exists() else pd.DataFrame()
    return editions, catalog


def _load_match_frames_from_db(conn: Any) -> tuple[pd.DataFrame, pd.DataFrame]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                ed.edition_id::text AS edition_id,
                ed.event_id::text AS event_id,
                c.canonical_name AS event_name,
                ed.event_year::text AS event_year,
                ed.event_month::text AS event_month
            FROM core.event_editions ed
            JOIN core.event_catalog c ON c.event_id = ed.event_id
            """
        )
        ed_cols = [d.name for d in cur.description]
        editions = pd.DataFrame(cur.fetchall(), columns=ed_cols)
        cur.execute(
            """
            SELECT event_id::text AS event_id, canonical_name, url
            FROM core.event_catalog
            """
        )
        cat_cols = [d.name for d in cur.description]
        catalog = pd.DataFrame(cur.fetchall(), columns=cat_cols)
    return editions, catalog


def save_calendar_artifacts(
    events: list[dict[str, Any]],
    matched: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    raw_count: int,
    min_start: date | None,
    source: str = CALENDAR_URL,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    current_doc = {
        "scraped_at": now.isoformat(),
        "source": source,
        "min_start": min_start.isoformat() if min_start else None,
        "raw_count": raw_count,
        "event_count": len(events),
        "events": events,
    }
    CURRENT_PATH.write_text(json.dumps(current_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(CSV_PATH, events, CSV_FIELDS)

    match_fields = CSV_FIELDS + [
        "matched_event_id",
        "matched_edition_id",
        "matched_event_name",
        "matched_event_year",
        "matched_event_month",
        "match_via",
        "match_status",
    ]
    _write_csv(MATCHED_CSV_PATH, matched, match_fields)
    REPORT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return current_doc


def sync_events_calendar(
    *,
    min_start: date | None = date(2025, 1, 1),
    skip_db: bool = False,
    conn: Any | None = None,
    rebuild_catalog: bool = False,
) -> dict[str, Any]:
    """Scrape calendar, match, save artifacts; optionally upsert DB.

    When ``conn`` is provided, uses that connection (caller owns commit).
    """
    raw = scrape_events_calendar()
    events = normalize_calendar_events(raw, min_start=min_start)

    own_conn = False
    if not skip_db and conn is None:
        from connection import connect

        conn = connect()
        own_conn = True

    try:
        if conn is not None and not skip_db:
            editions, catalog = _load_match_frames_from_db(conn)
        else:
            editions, catalog = _load_match_frames_from_csv()

        if editions.empty:
            matched, summary = [], {
                "total": len(events),
                "matched": 0,
                "event_only": 0,
                "unmatched": len(events),
                "by_via": {},
            }
        else:
            matched, summary = match_calendar_to_editions(events, editions, catalog)

        save_calendar_artifacts(
            events,
            matched,
            summary,
            raw_count=len(raw),
            min_start=min_start,
        )

        result: dict[str, Any] = {
            "raw_count": len(raw),
            "event_count": len(events),
            "match": summary,
            "upserted": 0,
            "enriched": (0, 0),
        }

        if conn is not None and not skip_db:
            from edition_calendar import (
                enrich_event_editions_dates,
                rows_for_upsert,
                upsert_edition_calendar_dates,
            )

            # Persist matched + event_only (known event_id, future editions).
            upsert_rows = rows_for_upsert(
                [r for r in matched if r.get("matched_event_id")],
                scraped_at=datetime.now(timezone.utc),
            )
            result["upserted"] = upsert_edition_calendar_dates(conn, upsert_rows)

            if rebuild_catalog:
                from build_event_catalog import rebuild_event_catalog

                rebuild_event_catalog(conn)
            else:
                result["enriched"] = enrich_event_editions_dates(conn)

            if own_conn:
                conn.commit()

        return result
    finally:
        if own_conn and conn is not None:
            conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--min-start",
        default="2025-01-01",
        help="ISO date; keep rows with start_date >= this (default: 2025-01-01)",
    )
    parser.add_argument(
        "--all-years",
        action="store_true",
        help="Keep every calendar row (ignore --min-start)",
    )
    parser.add_argument("--skip-db", action="store_true", help="Artifacts only")
    parser.add_argument(
        "--rebuild-catalog",
        action="store_true",
        help="Full rebuild_event_catalog after upsert (otherwise enrich only)",
    )
    args = parser.parse_args()

    min_start: date | None
    if args.all_years:
        min_start = None
    else:
        min_start = date.fromisoformat(args.min_start)

    result = sync_events_calendar(
        min_start=min_start,
        skip_db=args.skip_db,
        rebuild_catalog=args.rebuild_catalog,
    )
    print(
        f"Scraped {result['raw_count']} raw → {result['event_count']} normalized "
        f"(min_start={min_start})"
    )
    m = result["match"]
    print(
        f"Match: {m.get('matched', 0)}/{m.get('total', 0)} editions "
        f"(event_only={m.get('event_only', 0)}, unmatched={m.get('unmatched', 0)})"
    )
    if not args.skip_db:
        print(f"Upserted durable dates: {result['upserted']}")
        print(f"Enriched editions (calendar, list): {result['enriched']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

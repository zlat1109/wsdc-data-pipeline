#!/usr/bin/env python3
"""Analyze mapping between Events List and points catalog (core.events).

Usage:
    python scripts/analyze_events_list_mapping.py
    python scripts/analyze_events_list_mapping.py --from-db
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from transform.events_list_catalog import load_catalog  # noqa: E402
from transform.events_list_mapping import analyze_mapping  # noqa: E402

REPORT_DIR = PROJECT_ROOT / "data" / "events_list" / "mapping"
CURRENT_PATH = PROJECT_ROOT / "data" / "events_list" / "current.json"


def load_scheduled(from_db: bool, *, editions: bool = False) -> list[dict]:
    if from_db:
        from connection import connect

        table = "core.scheduled_events" if editions else "core.events_list_current"
        extra = ", is_active" if editions else ""
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT source_fingerprint, event_name, start_date, end_date,
                       location_raw, url, status_event{extra}
                FROM {table}
                {"WHERE is_active = true" if editions else ""}
                ORDER BY start_date, event_name
                """
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
            if not editions:
                for row in rows:
                    row.setdefault("is_active", True)
            return rows

    data = json.loads(CURRENT_PATH.read_text(encoding="utf-8"))
    return data.get("events") or []


def print_summary(report: dict) -> None:
    s = report["summary"]
    print("\n=== Events List ↔ Points catalog mapping ===")
    print(f"Active on schedule: {s['scheduled_active']}")
    print(f"Confirmed match:    {s['confirmed']}")
    print(f"Suggested (fuzzy):  {s['suggested']}")
    print(f"Manual review:      {s['review']}")
    print(f"New / unmapped:     {s['new_unmapped']}")
    print(f"Location drifts:    {s['location_drifts']}")
    print(f"Name variants:      {s['name_variants']}")

    if report.get("new_events"):
        print("\n--- New / unmapped (sample) ---")
        for ev in report["new_events"][:12]:
            print(f"  ? {ev['list_name']} ({ev['start_date']}) — {ev['location_raw'][:50]}")

    if report.get("location_drifts"):
        print("\n--- Location drift (sample) ---")
        for ev in report["location_drifts"][:10]:
            print(f"  ! {ev['list_name']} → {ev['canonical_name']}")
            print(f"    list:     {ev['location_raw']}")
            print(f"    typical:  {ev['typical_location']} (score {ev['location_score']:.2f})")

    if report.get("name_variants"):
        print("\n--- Name variants (URL/explicit confirmed, sample) ---")
        for ev in report["name_variants"][:10]:
            if ev["match_status"] == "confirmed":
                print(f"  ~ {ev['list_name']!r} → {ev['canonical_name']!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-db", action="store_true", help="Read scheduled from Supabase")
    parser.add_argument(
        "--editions",
        action="store_true",
        help="With --from-db: read edition archive instead of one-row-per-event current",
    )
    args = parser.parse_args()

    scheduled = load_scheduled(args.from_db, editions=args.editions)
    catalog = load_catalog()
    report = analyze_mapping(scheduled, catalog)
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["catalog_events"] = len(catalog)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = REPORT_DIR / f"mapping_{stamp}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPORT_DIR / "latest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print_summary(report)
    print(f"\nReport: {out}")


if __name__ == "__main__":
    main()

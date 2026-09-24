#!/usr/bin/env python3
"""One-shot: fill month-stub edition dates from WSDC clone ``competitionevents``.

Does **not** run on every parse. Durable write → ``core.edition_calendar_dates``
(``date_source=wsdc_dump``) then enrich ``event_editions``. Day≠day conflicts
are reported only.

Input (non-PII TSV, gitignored under ``dumps/``):
  id \\t event_id \\t event_name \\t start_date \\t end_date

Match: ``competitionevents.event_id`` (series) → MERGE map → existing edition.
``competitionevents.id`` is the per-edition PK and is **not** our registry id.

Usage:
    python scripts/sync_dump_edition_dates.py --dry-run
    python scripts/sync_dump_edition_dates.py --apply
    python scripts/sync_dump_edition_dates.py --apply --export --build-year-calendar

After apply, refresh dependents (export CSVs already expose start_date/end_date):
    python export.py --output-dir data
    python scripts/build_year_event_calendar.py --data-dir data
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

DEFAULT_TSV = PROJECT_ROOT / "dumps" / "competitionevents_dates.tsv"
REPORT_DIR = PROJECT_ROOT / "data" / "quality_reports"


def _load_editions_from_db(conn) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                ed.event_id,
                ed.event_year,
                ed.event_month,
                ed.start_date,
                ed.end_date,
                COALESCE(c.canonical_name, e.name, '') AS event_name
            FROM core.event_editions ed
            LEFT JOIN core.event_catalog c ON c.event_id = ed.event_id
            LEFT JOIN core.events e ON e.event_id = ed.event_id
            """
        )
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def _load_editions_from_csv(path: Path) -> list[dict]:
    import pandas as pd

    df = pd.read_csv(path, dtype=str)
    rows: list[dict] = []
    for rec in df.to_dict(orient="records"):
        rows.append(
            {
                "event_id": int(float(rec["event_id"])),
                "event_year": int(float(rec["event_year"])),
                "event_month": int(float(rec["event_month"])),
                "start_date": rec.get("start_date"),
                "end_date": rec.get("end_date"),
                "event_name": rec.get("event_name") or "",
            }
        )
    return rows


def _write_report(plans, summary: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    from transform.dump_edition_dates import plans_as_dicts

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "plans": plans_as_dicts(plans),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Flat CSV for conflict / fill review
    csv_path = path.with_suffix(".csv")
    fields = [
        "action",
        "dump_competitionevent_id",
        "dump_series_event_id",
        "canonical_event_id",
        "event_year",
        "event_month",
        "event_name",
        "dump_start",
        "dump_end",
        "ours_start",
        "ours_end",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in payload["plans"]:
            if row["action"] in {"fill", "conflict", "no_edition", "skip_duplicate"}:
                writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--tsv",
        type=Path,
        default=DEFAULT_TSV,
        help=f"competitionevents dates TSV (default: {DEFAULT_TSV})",
    )
    parser.add_argument(
        "--editions-csv",
        type=Path,
        default=None,
        help="Use local event_editions.csv instead of DB (dry-run only)",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=REPORT_DIR / "dump_edition_dates_report.json",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="After apply: run export.py for edition CSVs",
    )
    parser.add_argument(
        "--build-year-calendar",
        action="store_true",
        help="After apply (+ optional export): rebuild year calendar JSON",
    )
    args = parser.parse_args()

    if not args.tsv.exists():
        print(f"Missing TSV: {args.tsv}")
        print(
            "Export from local wsdc-clone, e.g.\n"
            "  docker exec wsdc-clone bash -c "
            "'mysql -uroot -p\"$MYSQL_ROOT_PASSWORD\" wsdc "
            "--default-character-set=utf8mb4 -N -B -e "
            "\"SELECT id, event_id, IFNULL(event_name,\\\"\\\"), "
            "IFNULL(start_date,\\\"\\\"), IFNULL(end_date,\\\"\\\") "
            "FROM competitionevents\"' > dumps/competitionevents_dates.tsv"
        )
        return 1

    from transform.dump_edition_dates import (
        fill_rows_for_upsert,
        load_competitionevents_tsv,
        plan_dump_edition_dates,
        summarize_plans,
    )

    dump_rows = load_competitionevents_tsv(args.tsv)
    print(f"dump rows: {len(dump_rows)} from {args.tsv}")

    if args.editions_csv is not None:
        if args.apply:
            print("--editions-csv cannot be used with --apply")
            return 2
        editions = _load_editions_from_csv(args.editions_csv)
        print(f"editions: {len(editions)} from {args.editions_csv}")
        plans = plan_dump_edition_dates(dump_rows, editions)
        summary = summarize_plans(plans)
        print("summary:", summary)
        _write_report(plans, summary, args.report)
        print(f"report: {args.report}")
        print("dry-run only — no writes")
        return 0

    from connection import connect
    from edition_calendar import (
        enrich_event_editions_dates,
        upsert_edition_calendar_dates,
    )

    with connect() as conn:
        editions = _load_editions_from_db(conn)
        print(f"editions: {len(editions)} from DB")
        plans = plan_dump_edition_dates(dump_rows, editions)
        summary = summarize_plans(plans)
        print("summary:", summary)
        _write_report(plans, summary, args.report)
        print(f"report: {args.report}")

        fills = fill_rows_for_upsert(plans)
        print(f"fill upserts: {len(fills)}")
        if args.dry_run:
            print("dry-run only — no writes")
            return 0

        upserted = upsert_edition_calendar_dates(conn, fills)
        # enrich also runs fill_edition_month_stub_dates (NULL → edition_date).
        cal_n, list_n = enrich_event_editions_dates(conn)
        conn.commit()
        print(f"upserted={upserted} enrich_calendar={cal_n} enrich_list={list_n}")

    if args.export or args.build_year_calendar:
        import subprocess

        if args.export:
            cmd = [
                sys.executable,
                str(PROJECT_ROOT / "export.py"),
                "--output-dir",
                str(PROJECT_ROOT / "data"),
            ]
            print("running:", " ".join(cmd))
            subprocess.check_call(cmd)

        if args.build_year_calendar:
            cmd = [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "build_year_event_calendar.py"),
                "--data-dir",
                str(PROJECT_ROOT / "data"),
            ]
            print("running:", " ".join(cmd))
            subprocess.check_call(cmd)

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build / merge Point Summary entities into the analytics site JSON.

Usage:
    python scripts/build_points_summary.py \\
      --data-dir data --site-repo /tmp/wsdc-site \\
      --cutoff 2026-07-28 --update-window-days 30 [--dry-run]

Writes static/data/points_summaries.json under --site-repo (or --output).
Emits a machine-readable report to --report (default:
data/quality_reports/point_summary_last.json).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from transform.points_summary import (  # noqa: E402
    build_full_event_report,
    clear_points_cache,
    edition_meta_from_row,
    load_dancers_map,
    load_results_rows,
    load_summaries,
    make_event_slug,
    merge_points_summaries,
    write_summaries,
)

DEFAULT_CUTOFF = date(2026, 7, 28)
SITE_REL = Path("static/data/points_summaries.json")


def _parse_date(value: str) -> date:
    return date.fromisoformat(value.strip())


def load_editions(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def build_candidates(
    data_dir: Path,
    *,
    cutoff: date,
    today: date | None = None,
    update_window_days: int = 30,
) -> list[dict]:
    today = today or date.today()
    editions = load_editions(data_dir / "event_editions.csv")
    results_rows = load_results_rows(data_dir / "dancers_results_info.csv")
    dancers_map = load_dancers_map(data_dir / "dancer_role_info.csv")
    points_csv = data_dir / "dancers_points_info.csv"
    clear_points_cache()

    window_start = today - timedelta(days=update_window_days)
    # Also rebuild a bit before cutoff so merge can update near-window editions.
    scan_from = min(cutoff, window_start) - timedelta(days=14)

    candidates: list[dict] = []
    for row in editions:
        meta = edition_meta_from_row(row)
        start = meta.get("start_date")
        if not start:
            continue
        start_d = date.fromisoformat(start)
        end_d = date.fromisoformat(meta["end_date"]) if meta.get("end_date") else start_d
        if end_d < scan_from and start_d < scan_from:
            continue

        report = build_full_event_report(meta, results_rows, dancers_map, points_csv)
        if not report:
            continue
        slug = make_event_slug(meta["name"], start)
        report["slug"] = slug
        report["start_date"] = meta.get("start_date")
        report["end_date"] = meta.get("end_date")
        candidates.append(report)
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument(
        "--site-repo",
        type=Path,
        default=None,
        help="Analytics site checkout; writes static/data/points_summaries.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Explicit output path (overrides --site-repo default path)",
    )
    parser.add_argument(
        "--existing",
        type=Path,
        default=None,
        help="Existing points_summaries.json to merge into (default: output path)",
    )
    parser.add_argument("--cutoff", type=_parse_date, default=DEFAULT_CUTOFF)
    parser.add_argument("--update-window-days", type=int, default=30)
    parser.add_argument(
        "--today",
        type=_parse_date,
        default=None,
        help="Override 'today' for post_date / window (tests)",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "data" / "quality_reports" / "point_summary_last.json",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-entries", type=int, default=52)
    args = parser.parse_args()

    if args.output:
        out_path = args.output
    elif args.site_repo:
        out_path = args.site_repo / SITE_REL
    else:
        out_path = PROJECT_ROOT / "data" / "points_summaries.json"

    existing_path = args.existing or out_path
    existing = load_summaries(existing_path)

    required = [
        "event_editions.csv",
        "dancers_results_info.csv",
        "dancer_role_info.csv",
        "dancers_points_info.csv",
    ]
    for name in required:
        if not (args.data_dir / name).exists():
            print(f"ERROR: missing {args.data_dir / name}", file=sys.stderr)
            return 1

    print(
        f"Building Point Summary candidates from {args.data_dir} "
        f"(cutoff={args.cutoff.isoformat()}, window={args.update_window_days}d)"
    )
    candidates = build_candidates(
        args.data_dir,
        cutoff=args.cutoff,
        today=args.today,
        update_window_days=args.update_window_days,
    )
    print(f"Candidates with top-3: {len(candidates)}")

    payload, report = merge_points_summaries(
        existing,
        candidates,
        cutoff=args.cutoff,
        update_window_days=args.update_window_days,
        today=args.today,
        max_entries=args.max_entries,
    )
    report["output"] = str(out_path)
    report["cutoff"] = args.cutoff.isoformat()
    report["candidate_count"] = len(candidates)
    report["dry_run"] = bool(args.dry_run)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"Point Summary: +{report['created_count']} created, "
        f"{report['updated_count']} updated, "
        f"{len(report['skipped'])} skipped"
    )
    for slug in report["created"][:20]:
        print(f"  + {slug}")
    if len(report["created"]) > 20:
        print(f"  ... +{len(report['created']) - 20} more")

    if args.dry_run:
        print(f"Dry run — not writing {out_path}")
        print(f"Report: {args.report}")
        return 0

    write_summaries(out_path, payload)
    print(f"Wrote {out_path}")
    print(f"Report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

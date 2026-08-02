#!/usr/bin/env python3
"""Build events_year_calendar.json for the analytics site.

Usage:
    python scripts/build_year_event_calendar.py \\
      --data-dir data --site-repo /path/to/wsdc-analytics.github.io

    python scripts/build_year_event_calendar.py --data-dir data --output /tmp/out.json
    python scripts/build_year_event_calendar.py --data-dir data --spike 2025 2026
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from transform.year_event_calendar.build import (  # noqa: E402
    build_year_event_calendar,
    spike_expected_accuracy,
    write_year_event_calendar,
)

SITE_REL = Path("static/data/events_year_calendar.json")


def _parse_date(value: str) -> date:
    return date.fromisoformat(value.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument("--site-repo", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--as-of", type=_parse_date, default=None)
    parser.add_argument("--year-radius", type=int, default=2)
    parser.add_argument(
        "--spike",
        nargs=2,
        type=int,
        metavar=("PRIOR_YEAR", "TARGET_YEAR"),
        help="Print YoY expected match spike report and exit",
    )
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()

    if args.spike:
        prior_y, target_y = args.spike
        report = spike_expected_accuracy(
            args.data_dir, prior_year=prior_y, target_year=target_y
        )
        print(json.dumps(report, indent=2))
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return 0

    payload = build_year_event_calendar(
        args.data_dir,
        as_of=args.as_of,
        year_radius=args.year_radius,
    )

    if args.output:
        out = args.output
    elif args.site_repo:
        out = Path(args.site_repo) / SITE_REL
    else:
        out = PROJECT_ROOT / "data" / "quality_reports" / "events_year_calendar.json"

    write_year_event_calendar(payload, out)
    summary = {
        "output": str(out),
        "as_of": payload["as_of"],
        "years": payload["years"],
        "event_count": len(payload["events"]),
        "counts_by_year": payload["counts_by_year"],
        "status_counts": {},
    }
    for ev in payload["events"]:
        st = ev["status"]
        summary["status_counts"][st] = summary["status_counts"].get(st, 0) + 1
    print(json.dumps(summary, indent=2))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

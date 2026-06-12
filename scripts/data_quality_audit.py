#!/usr/bin/env python3
"""Run data quality audit on exported CSVs and write a review log.

Usage:
    python scripts/data_quality_audit.py
    python scripts/data_quality_audit.py --data-dir data --source github-actions
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from transform.quality_audit import (  # noqa: E402
    finalize_report,
    load_csv_bundle,
    load_previous_report,
    mark_new_findings,
    run_audit,
)

DEFAULT_REPORT_DIR = PROJECT_ROOT / "data" / "quality_reports"


def print_summary(report: dict) -> None:
    summary = report["summary"]
    print(f"\n=== Data quality audit ===")
    print(f"Total findings: {summary['total_findings']}")
    print(f"New since last run: {summary['new_findings']}")
    if summary.get("by_severity"):
        print(f"By severity: {summary['by_severity']}")
    if summary.get("by_category"):
        print(f"By category: {summary['by_category']}")

    for finding in report["findings"]:
        if not finding.get("is_new"):
            continue
        flag = "🆕" if finding.get("is_new") else "  "
        print(
            f"\n{flag} [{finding['severity'].upper()}] "
            f"{finding['category']}.{finding['code']} (n={finding.get('count', 0)})"
        )
        print(f"   {finding['message']}")
        if finding.get("suggested_fix"):
            print(f"   → {finding['suggested_fix']}")
        for ex in (finding.get("examples") or [])[:3]:
            print(f"   • {ex}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--source", default="local")
    parser.add_argument("--run-id", type=int, default=None)
    args = parser.parse_args()

    data = load_csv_bundle(args.data_dir)
    if not data:
        print(f"No CSV files found in {args.data_dir}")
        sys.exit(1)

    args.report_dir.mkdir(parents=True, exist_ok=True)
    latest_path = args.report_dir / "latest.json"
    prev_fps, prev_names = load_previous_report(latest_path)

    findings = run_audit(data, previous_event_names=prev_names or None)
    mark_new_findings(findings, prev_fps)

    report = finalize_report(
        data,
        findings,
        source=args.source,
        run_id=args.run_id,
    )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stamped_path = args.report_dir / f"quality_{stamp}.json"
    stamped_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print_summary(report)
    print(f"\nReport: {stamped_path}")
    print(f"Latest: {latest_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Preprocess CSVs with normalization + combined quality log.

Flow:
  1. Audit raw data (before_processing)
  2. Apply known maps + auto-patterns (applied_normalizations)
  3. Audit processed data → manual_review_required
  4. Write processed CSVs back to data_dir

Usage:
    python scripts/preprocess_data.py --data-dir data
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from transform.preprocess_with_log import (  # noqa: E402
    build_combined_report,
    preprocess_with_log,
)
from transform.quality_audit import load_csv_bundle, load_previous_report  # noqa: E402

DEFAULT_REPORT_DIR = PROJECT_ROOT / "data" / "quality_reports"

OUTPUT_FILES = {
    "location_info": "location_info.csv",
    "events_wsdc": "events_wsdc.csv",
    "dancers_results_info": "dancers_results_info.csv",
    "dancer_role_info": "dancer_role_info.csv",
    "dancers_points_info": "dancers_points_info.csv",
}


def save_csv_bundle(data_dir: Path, data: dict) -> None:
    for key, filename in OUTPUT_FILES.items():
        if key in data:
            data[key].to_csv(data_dir / filename, index=False)


def print_summary(report: dict) -> None:
    s = report["summary"]
    print("\n=== Preprocess + quality log ===")
    print(f"Before processing: {s['before_findings_count']} findings")
    print(f"Applied rules: {s['applied_rules_count']} ({s['applied_rows_touched']} row hits)")
    print(f"Manual review: {s['manual_review_count']} ({s['manual_review_new_count']} new)")

    applied = report.get("applied_normalizations", {}).get("rules", [])
    if applied:
        print("\nApplied normalizations (sample):")
        for rule in applied[:8]:
            print(
                f"  [{rule['source']}] {rule['rule_id']}: "
                f"{rule['from_value']!r} → {rule['to_value']!r} "
                f"({rule['rows_affected']} rows, {rule['table']}.{rule['column']})"
            )
        if len(applied) > 8:
            print(f"  ... +{len(applied) - 8} more")

    manual = report.get("manual_review_required", {}).get("findings", [])
    new_manual = [f for f in manual if f.get("is_new")]
    if new_manual:
        print("\nManual review required (new):")
        for f in new_manual[:8]:
            print(f"  [{f.get('severity')}] {f.get('code')}: {f.get('message')}")
            for ex in (f.get("examples") or [])[:2]:
                print(f"    • {ex}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--source", default="local")
    parser.add_argument("--run-id", type=int, default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not overwrite CSV files",
    )
    args = parser.parse_args()

    raw_data = load_csv_bundle(args.data_dir)
    if not raw_data:
        print(f"No CSV files in {args.data_dir}")
        sys.exit(1)

    raw_snapshot = {k: v.copy() for k, v in raw_data.items()}
    processed, tracker = preprocess_with_log(raw_data)

    args.report_dir.mkdir(parents=True, exist_ok=True)
    latest_path = args.report_dir / "latest.json"
    prev_fps, prev_names = load_previous_report(latest_path)

    report = build_combined_report(
        raw_snapshot,
        processed,
        tracker,
        previous_fingerprints=prev_fps,
        previous_event_names=prev_names or None,
        source=args.source,
        run_id=args.run_id,
    )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stamped_path = args.report_dir / f"quality_{stamp}.json"
    stamped_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.dry_run:
        save_csv_bundle(args.data_dir, processed)
        print(f"\nProcessed CSVs written to {args.data_dir}")

    print_summary(report)
    print(f"\nReport: {stamped_path}")


if __name__ == "__main__":
    main()

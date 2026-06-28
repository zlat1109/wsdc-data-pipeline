#!/usr/bin/env python3
"""Run post-load quality checks against Supabase.

Usage:
    python scripts/validate_supabase_quality.py              # core + extended
    python scripts/validate_supabase_quality.py --core-only  # CI-compatible subset
    python scripts/validate_supabase_quality.py --json       # machine-readable report
    python scripts/validate_supabase_quality.py --json -o data/quality_reports/supabase_latest.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from quality_checks import ALL_CHECKS, CORE_CHECKS, run_quality_checks  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-only", action="store_true", help="Run only CI core checks")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write JSON report to file (implies structured output)",
    )
    args = parser.parse_args()

    checks = CORE_CHECKS if args.core_only else ALL_CHECKS
    report = run_quality_checks(checks)
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["scope"] = "core" if args.core_only else "full"

    if args.json or args.output:
        payload = json.dumps(report, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload + "\n", encoding="utf-8")
            print(f"Wrote {args.output}", flush=True)
        if args.json:
            print(payload)
    else:
        for r in report["checks"]:
            status = "OK" if r["ok"] else r["severity"].upper()
            print(
                f"[{status}] {r['name']}: {r['value']} "
                f"(expected <= {r['max_value']}) — {r['category']}"
            )
            if not r["ok"] and r["fix_hint"]:
                print(f"         fix: {r['fix_hint']}")
        s = report["summary"]
        print(
            f"\nSummary: {s['passed']}/{s['total']} passed, "
            f"{s['errors']} error(s), {s['warnings']} warning(s)"
        )

    return 1 if int(report["summary"]["errors"]) > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

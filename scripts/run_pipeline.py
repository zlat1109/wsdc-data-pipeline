#!/usr/bin/env python3
"""Run the post-parse pipeline: migrations -> preprocess -> load -> export.

Usage:
    python scripts/run_pipeline.py --data-dir "/path/to/csv"
    python scripts/run_pipeline.py --export-only
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> None:
    print(f"\n>> {' '.join(cmd)}")
    subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        help="Directory with parser CSV output (for load.py)",
    )
    parser.add_argument(
        "--source",
        default="github-actions",
        choices=["local", "github-actions"],
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Skip load/backfill; export current Supabase state to data/",
    )
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="Skip db/apply.py",
    )
    args = parser.parse_args()

    py = sys.executable

    if not args.skip_migrations:
        run([py, "db/apply.py"])

    if not args.export_only:
        if not args.data_dir:
            sys.exit("--data-dir is required unless --export-only is set")
        run([
            py,
            "scripts/validate_pipeline_inputs.py",
            "--data-dir",
            str(args.data_dir),
        ])
        run([
            py,
            "scripts/preprocess_data.py",
            "--data-dir",
            str(args.data_dir),
            "--source",
            args.source,
        ])
        run([py, "load.py", "--data-dir", str(args.data_dir), "--source", args.source])
        run([py, "scripts/reconcile_points_history.py", "--apply"])
        run([py, "scripts/reconcile_roles_history.py", "--apply"])
        run([py, "scripts/reconcile_names_history.py", "--apply"])
        run([py, "scripts/repair_divisions.py", "--apply"])
        run([py, "scripts/repair_locations.py"])
        run([py, "scripts/merge_location_ids.py", "--apply"])
        run([py, "scripts/dedupe_core_data.py", "--apply"])

    # Always gate on DB quality before writing CSVs — including --export-only,
    # which is the path used to refresh Tableau delivery files. Full check set
    # (not --core-only) so location uniqueness / orphan gates always run.
    run([
        py,
        "scripts/validate_supabase_quality.py",
        "-o",
        "data/quality_reports/supabase_pre_export.json",
    ])

    run([py, "export.py"])

    run([
        py,
        "scripts/validate_export_vs_db.py",
        "--data-dir",
        "data",
    ])

    if not args.export_only:
        run([
            py,
            "scripts/validate_supabase_quality.py",
            "-o",
            "data/quality_reports/supabase_latest.json",
        ])

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Gate: exported data/*.csv row counts must match export.* views in Supabase.

Prevents committing a partial/stale CSV set after a failed or skipped export.
Used by full-parse.yml before the CSV commit step, and by run_pipeline.py
after export.py.

Usage:
    python scripts/validate_export_vs_db.py
    python scripts/validate_export_vs_db.py --data-dir ./data
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from connection import connect  # noqa: E402

# Views that feed the Tableau / bot delivery contract.
# Keep this as an allowlist — never interpolate untrusted identifiers into SQL.
EXPORT_CHECKS: tuple[tuple[str, str], ...] = (
    ("export.dancers_results_info", "dancers_results_info.csv"),
    ("export.dancers_points_info", "dancers_points_info.csv"),
    ("export.dancer_role_info", "dancer_role_info.csv"),
    ("export.location_info", "location_info.csv"),
    ("export.events_wsdc", "events_wsdc.csv"),
)
_ALLOWED_VIEWS = frozenset(view for view, _ in EXPORT_CHECKS)


def _csv_rows(path: Path) -> int:
    if not path.exists():
        return -1
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        try:
            next(reader)  # header
        except StopIteration:
            return 0
        return sum(1 for _ in reader)


def _view_rows(cur, view: str) -> int:
    if view not in _ALLOWED_VIEWS:
        raise ValueError(f"Refusing to query non-allowlisted view: {view!r}")
    cur.execute(f"SELECT count(*) FROM {view}")
    return int(cur.fetchone()[0])


def _scheduled_events_health_problem(data_dir: Path) -> str | None:
    """Return gate error when schedule export is header-only / empty."""
    path = data_dir / "scheduled_events.csv"
    rows = _csv_rows(path)
    if rows < 0:
        return "scheduled_events.csv: missing on disk"
    if rows == 0:
        return (
            "scheduled_events.csv: 0 data rows (header-only). "
            "Health-check failed: would publish empty schedule."
        )
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=PROJECT_ROOT / "data",
    )
    parser.add_argument(
        "--tolerance",
        type=int,
        default=0,
        help="Allowed absolute row-count delta (default 0)",
    )
    args = parser.parse_args()

    problems: list[str] = []
    schedule_problem = _scheduled_events_health_problem(args.data_dir)
    if schedule_problem:
        problems.append(schedule_problem)
        print("[FAIL] scheduled_events.csv health-check")
    else:
        print("[OK] scheduled_events.csv health-check")

    with connect() as conn:
        with conn.cursor() as cur:
            for view, filename in EXPORT_CHECKS:
                csv_path = args.data_dir / filename
                db_n = _view_rows(cur, view)
                csv_n = _csv_rows(csv_path)
                if csv_n < 0:
                    problems.append(f"{filename}: missing on disk (DB {view}={db_n})")
                    continue
                delta = abs(db_n - csv_n)
                status = "OK" if delta <= args.tolerance else "FAIL"
                print(f"[{status}] {filename}: csv={csv_n:,} db={db_n:,} delta={delta}")
                if delta > args.tolerance:
                    problems.append(
                        f"{filename}: csv={csv_n} vs {view}={db_n} (delta {delta})"
                    )

    # Join integrity on the exported pair (same contract Tableau uses).
    results_path = args.data_dir / "dancers_results_info.csv"
    loc_path = args.data_dir / "location_info.csv"
    if results_path.exists() and loc_path.exists():
        results = pd.read_csv(
            results_path, usecols=["location_id"], dtype={"location_id": "Int64"}
        )
        locs = pd.read_csv(
            loc_path, usecols=["location_id"], dtype={"location_id": "Int64"}
        )
        referenced = set(results["location_id"].dropna().astype(int))
        available = set(locs["location_id"].dropna().astype(int))
        orphans = referenced - available
        if orphans:
            sample = sorted(orphans)[:5]
            problems.append(
                f"location join: {len(orphans)} location_id in results missing "
                f"from location_info (e.g. {sample})"
            )
            print(f"[FAIL] location join orphans={len(orphans)}")
        else:
            print(
                f"[OK] location join: {len(referenced):,} referenced ids "
                f"all present in {len(available):,} locations"
            )

    if problems:
        print("\nExport vs DB gate FAILED:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print("\nExport vs DB gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

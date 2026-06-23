#!/usr/bin/env python3
"""Pre-flight checks for parser CSVs before preprocess/load.

Catches common load failures locally (minutes) instead of after a 4h cloud parse.

Usage:
    python scripts/validate_pipeline_inputs.py --data-dir ./data
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from transform.data_preprocessing import results_date_parse_rate  # noqa: E402

REQUIRED_CSV = (
    "dancer_role_info.csv",
    "dancers_points_info.csv",
    "dancers_results_info.csv",
    "location_info.csv",
    "events_wsdc.csv",
)

NUMERIC_ID = re.compile(r"^\d+$")
VALID_EVENT_ROLES = frozenset({"leader", "follower"})
VALID_POINT_ROLES = frozenset({"leader", "follower"})


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _numeric_ids(series: pd.Series, label: str, report: ValidationReport) -> set[int]:
    ids: set[int] = set()
    for raw in series.fillna(""):
        value = str(raw).strip()
        if not value:
            continue
        if not NUMERIC_ID.match(value):
            report.error(f"{label}: non-numeric dancer_id {value!r}")
            continue
        ids.add(int(value))
    return ids


def validate_pipeline_inputs(data_dir: Path) -> ValidationReport:
    report = ValidationReport()

    if not data_dir.is_dir():
        report.error(f"Data directory not found: {data_dir}")
        return report

    for name in REQUIRED_CSV:
        if not (data_dir / name).exists():
            report.error(f"Missing required CSV: {name}")

    if report.errors:
        return report

    role = _read_csv(data_dir / "dancer_role_info.csv")
    points = _read_csv(data_dir / "dancers_points_info.csv")
    results = _read_csv(data_dir / "dancers_results_info.csv")

    for col, frame, label in (
        ("dancer_id", role, "dancer_role_info"),
        ("dancer_id", points, "dancers_points_info"),
        ("dancer_id", results, "dancers_results_info"),
    ):
        if col not in frame.columns:
            report.error(f"{label}: missing column {col!r}")

    if report.errors:
        return report

    role_ids = _numeric_ids(role["dancer_id"], "dancer_role_info", report)
    points_ids = _numeric_ids(points["dancer_id"], "dancers_points_info", report)
    results_ids = _numeric_ids(results["dancer_id"], "dancers_results_info", report)
    all_ids = role_ids | points_ids | results_ids

    # promote_core.sql: dancer_roles from role; dancers from union(role, points, results)
    missing_for_dancers = (points_ids | results_ids) - all_ids
    if missing_for_dancers:
        report.error(
            f"dancer_id union mismatch: {len(missing_for_dancers)} ids "
            f"(sample: {sorted(missing_for_dancers)[:5]})"
        )

    empty_names = role[
        role["dancer_name"].fillna("").str.strip() == ""
    ]["dancer_id"].astype(str).str.strip()
    empty_name_ids = {int(x) for x in empty_names if NUMERIC_ID.match(x)}
    if empty_name_ids:
        report.warn(
            f"{len(empty_name_ids)} dancers with empty name in dancer_role_info "
            f"(OK after promote_core fix; sample ids: {sorted(empty_name_ids)[:5]})"
        )

    if "role" in points.columns:
        bad = {
            str(v).strip().lower()
            for v in points["role"].fillna("")
            if str(v).strip() and str(v).strip().lower() not in VALID_POINT_ROLES
        }
        if bad:
            report.error(f"dancers_points_info: invalid role values: {sorted(bad)[:8]}")

    if "event_role" in results.columns:
        bad = {
            str(v).strip().lower()
            for v in results["event_role"].fillna("")
            if str(v).strip() and str(v).strip().lower() not in VALID_EVENT_ROLES
        }
        if bad:
            report.error(f"dancers_results_info: invalid event_role values: {sorted(bad)[:8]}")

    if "event_name" in results.columns:
        empty_names = results["event_name"].fillna("").astype(str).str.strip() == ""
        null_rate = empty_names.mean()
        if null_rate > 0.01:
            report.error(
                f"dancers_results_info: {null_rate:.1%} rows missing event_name "
                f"({int(empty_names.sum())} rows). "
                "Do not load from export.dancers_results_info — use parser/cloud_parse output."
            )

    date_cols = {"event_year", "event_month", "event_year_and_month"} & set(results.columns)
    if date_cols:
        coverage = results_date_parse_rate(results)
        if coverage < 0.99:
            report.error(
                f"dancers_results_info: only {coverage:.1%} rows have parseable event dates "
                "(need >=99% before load; cloud parse should use Month Year or ISO)"
            )
        elif coverage < 1.0:
            report.warn(
                f"dancers_results_info: {coverage:.1%} rows have parseable event dates "
                f"({len(results) - int(coverage * len(results))} unparseable)"
            )

    role_only = role_ids - points_ids - results_ids
    if len(role_only) > 50:
        report.warn(
            f"{len(role_only)} dancer_ids only in dancer_role_info "
            "(no points/results rows — unusual but allowed)"
        )

    report.warn(f"Row counts: role={len(role)}, points={len(points)}, results={len(results)}")
    report.warn(f"Unique dancer_ids: role={len(role_ids)}, points={len(points_ids)}, results={len(results_ids)}")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=PROJECT_ROOT / "data",
        help="Directory with parser CSV files",
    )
    args = parser.parse_args()

    report = validate_pipeline_inputs(args.data_dir)

    for msg in report.warnings:
        print(f"WARN: {msg}", flush=True)
    for msg in report.errors:
        print(f"ERROR: {msg}", flush=True)

    if report.ok:
        print("Validation passed.", flush=True)
    else:
        print(f"Validation failed ({len(report.errors)} errors).", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

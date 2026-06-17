#!/usr/bin/env python3
"""Build merged parser CSV set from best available sources.

Base: old-laptop snapshot (freshest registry/points, ISO dates).
Supplement: main/local rows missing on old laptop (dancers, locations).
Results: union old-laptop + normalized Supabase staging (extra rows from GitHub parse).

Usage:
    python scripts/build_merged_load_dataset.py --output-dir data/merged_load
"""

from __future__ import annotations

import argparse
import io
import subprocess
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from transform.data_preprocessing import normalize_results_dates  # noqa: E402

CORE_FILES = (
    "dancer_role_info.csv",
    "dancers_points_info.csv",
    "dancers_results_info.csv",
    "location_info.csv",
    "events_wsdc.csv",
)

# Present on main / GitHub parse but missing on old-laptop 8cd31a5.
SUPPLEMENT_DANCER_IDS = ("13738", "17293")


def _read_git_csv(ref: str, name: str) -> pd.DataFrame:
    blob = subprocess.check_output(
        ["git", "show", f"{ref}:data/{name}"],
        stderr=subprocess.DEVNULL,
    )
    return pd.read_csv(io.BytesIO(blob), dtype=str, keep_default_na=False)


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _append_missing_rows(
    base: pd.DataFrame,
    supplement: pd.DataFrame,
    key_col: str,
    *,
    filter_ids: set[str] | None = None,
) -> pd.DataFrame:
    if supplement.empty or key_col not in supplement.columns:
        return base
    base_keys = set(base[key_col].astype(str).str.strip())
    rows = supplement[~supplement[key_col].astype(str).str.strip().isin(base_keys)]
    if filter_ids is not None:
        rows = rows[rows[key_col].astype(str).str.strip().isin(filter_ids)]
    if rows.empty:
        return base
    aligned = rows.reindex(columns=base.columns, fill_value="")
    return pd.concat([base, aligned], ignore_index=True)


def _results_key(df: pd.DataFrame) -> pd.Series:
    cols = [
        "dancer_id",
        "event_dance",
        "event_competition",
        "event_role",
        "event_year",
        "event_month",
    ]
    parts = []
    for col in cols:
        if col not in df.columns:
            parts.append(pd.Series([""] * len(df), index=df.index))
            continue
        series = df[col].fillna("").astype(str).str.strip()
        if col == "event_role":
            series = series.str.lower()
        parts.append(series)
    return parts[0].str.cat(parts[1:], sep="|")


def _merge_results(old_results: pd.DataFrame, staging_results: pd.DataFrame) -> pd.DataFrame:
    old_norm = normalize_results_dates(old_results)
    staging_norm = normalize_results_dates(staging_results)

    old_norm = old_norm.copy()
    staging_norm = staging_norm.copy()
    old_norm["_key"] = _results_key(old_norm)
    staging_norm["_key"] = _results_key(staging_norm)

    extra = staging_norm[~staging_norm["_key"].isin(old_norm["_key"])].drop(columns="_key")
    merged = pd.concat([old_norm.drop(columns="_key"), extra], ignore_index=True)
    return merged


def fetch_staging_results() -> pd.DataFrame:
    from connection import connect  # noqa: WPS433

    with connect() as conn:
        return pd.read_sql(
            "SELECT * FROM staging.dancers_results_info",
            conn,
            dtype=str,
        ).fillna("")


def build_merged_dataset(
    *,
    old_ref: str,
    supplement_dir: Path,
    output_dir: Path,
    use_staging_results: bool,
) -> dict[str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}

    old_frames = {name: _read_git_csv(old_ref, name) for name in CORE_FILES}
    supplement_frames = {name: _read_csv(supplement_dir / name) for name in CORE_FILES}

    role = _append_missing_rows(
        old_frames["dancer_role_info.csv"],
        supplement_frames["dancer_role_info.csv"],
        "dancer_id",
        filter_ids=set(SUPPLEMENT_DANCER_IDS),
    )
    points = old_frames["dancers_points_info.csv"]
    for did in SUPPLEMENT_DANCER_IDS:
        points = _append_missing_rows(points, supplement_frames["dancers_points_info.csv"], "dancer_id", filter_ids={did})

    if use_staging_results:
        staging = fetch_staging_results()
        results = _merge_results(old_frames["dancers_results_info.csv"], staging)
    else:
        results = normalize_results_dates(old_frames["dancers_results_info.csv"])

    locations = _append_missing_rows(
        old_frames["location_info.csv"],
        supplement_frames["location_info.csv"],
        "location_id",
    )
    events = old_frames["events_wsdc.csv"]

    for name, df in zip(
        CORE_FILES,
        [role, points, results, locations, events],
        strict=True,
    ):
        path = output_dir / name
        df.to_csv(path, index=False)
        counts[name] = len(df)

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-ref", default="8cd31a5")
    parser.add_argument("--supplement-dir", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data" / "merged_load")
    parser.add_argument(
        "--no-staging-results",
        action="store_true",
        help="Skip Supabase staging union for results",
    )
    args = parser.parse_args()

    counts = build_merged_dataset(
        old_ref=args.old_ref,
        supplement_dir=args.supplement_dir,
        output_dir=args.output_dir,
        use_staging_results=not args.no_staging_results,
    )
    print(f"Merged dataset written to {args.output_dir}")
    for name, n in counts.items():
        print(f"  {name}: {n} rows")


if __name__ == "__main__":
    main()

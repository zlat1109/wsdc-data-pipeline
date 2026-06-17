#!/usr/bin/env python3
"""Compare WSDC parser CSV snapshots across git refs / directories."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

CORE_FILES = (
    "dancer_role_info.csv",
    "dancers_points_info.csv",
    "dancers_results_info.csv",
    "location_info.csv",
    "events_wsdc.csv",
)

EXPORT_FILES = (
    "event_catalog.csv",
    "event_editions.csv",
    "scheduled_events.csv",
)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _date_stats(df: pd.DataFrame) -> dict[str, object]:
    if df.empty or "event_year_and_month" not in df.columns:
        return {}
    yam = df["event_year_and_month"].fillna("").astype(str).str.strip()
    year = df.get("event_year", pd.Series(dtype=str)).fillna("").astype(str).str.strip()
    month = df.get("event_month", pd.Series(dtype=str)).fillna("").astype(str).str.strip()
    iso = yam.str.match(r"^\d{4}-\d{2}-\d{2}$")
    month_year = yam.str.match(r"^[A-Za-z]+\s+\d{4}$")
    return {
        "with_year": int((year != "").sum()),
        "with_month": int((month != "").sum()),
        "with_yam": int((yam != "").sum()),
        "iso_yam": int(iso.sum()),
        "month_year_yam": int(month_year.sum()),
        "yam_sample": yam[yam != ""].head(2).tolist(),
    }


def _snapshot_stats(data_dir: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for name in CORE_FILES + EXPORT_FILES:
        path = data_dir / name
        df = _read_csv(path)
        if df.empty and not path.exists():
            continue
        info: dict[str, object] = {"rows": len(df), "cols": list(df.columns)}
        if name == "dancer_role_info.csv" and "dancer_id" in df.columns:
            ids = pd.to_numeric(df["dancer_id"], errors="coerce")
            info["max_dancer_id"] = int(ids.max()) if ids.notna().any() else None
            info["empty_names"] = int(
                (df.get("dancer_name", pd.Series(dtype=str)).fillna("").str.strip() == "").sum()
            )
        if name in {"dancers_points_info.csv", "dancers_results_info.csv"} and "dancer_id" in df.columns:
            info["unique_dancers"] = int(df["dancer_id"].nunique())
        if name == "dancers_results_info.csv":
            info.update(_date_stats(df))
        out[name] = info
    return out


def materialize_git_ref(ref: str, dest: Path) -> None:
    for name in CORE_FILES + EXPORT_FILES:
        path = f"data/{name}"
        try:
            blob = subprocess.check_output(
                ["git", "show", f"{ref}:{path}"],
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            continue
        (dest / name).write_bytes(blob)


def print_snapshot(label: str, stats: dict[str, dict]) -> None:
    print(f"\n{'=' * 60}\n{label}\n{'=' * 60}")
    for name, info in stats.items():
        print(f"\n{name}:")
        for k, v in info.items():
            print(f"  {k}: {v}")


def compare_ids(a: pd.DataFrame, b: pd.DataFrame, col: str = "dancer_id") -> dict[str, int]:
    if col not in a.columns or col not in b.columns:
        return {}
    sa = set(a[col].astype(str).str.strip()) - {""}
    sb = set(b[col].astype(str).str.strip()) - {""}
    return {
        "only_a": len(sa - sb),
        "only_b": len(sb - sa),
        "shared": len(sa & sb),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-dir", type=Path, default=Path("data"))
    parser.add_argument("--old-laptop-ref", default="8cd31a5")
    parser.add_argument("--main-ref", default="origin/main")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        old_dir = tmp_path / "old_laptop"
        main_dir = tmp_path / "main"
        old_dir.mkdir()
        main_dir.mkdir()

        materialize_git_ref(args.old_laptop_ref, old_dir)
        materialize_git_ref(args.main_ref, main_dir)

        local_stats = _snapshot_stats(args.local_dir.resolve())
        old_stats = _snapshot_stats(old_dir)
        main_stats = _snapshot_stats(main_dir)

        print_snapshot(f"THIS LAPTOP (working tree: {args.local_dir})", local_stats)
        print_snapshot(f"OLD LAPTOP (git {args.old_laptop_ref})", old_stats)
        print_snapshot(f"GITHUB REPO main ({args.main_ref}) — last committed export", main_stats)

        print(f"\n{'=' * 60}\nPAIRWISE dancer_id deltas\n{'=' * 60}")
        pairs = [
            ("old_laptop", old_dir, "this_laptop", args.local_dir.resolve()),
            ("old_laptop", old_dir, "main", main_dir),
            ("this_laptop", args.local_dir.resolve(), "main", main_dir),
        ]
        for label_a, dir_a, label_b, dir_b in pairs:
            for file in CORE_FILES[:3]:
                da = _read_csv(dir_a / file)
                db = _read_csv(dir_b / file)
                if da.empty or db.empty:
                    continue
                delta = compare_ids(da, db)
                if delta:
                    print(f"{file}: {label_a} vs {label_b} -> {delta}")


if __name__ == "__main__":
    main()

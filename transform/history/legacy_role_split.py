"""Shared SCD2 interval builders for legacy changed_dancer_role_info.csv."""

from __future__ import annotations

import re
import time
from pathlib import Path

import pandas as pd

from transform.normalize import normalize_dancer_name, normalize_level, normalize_role

NUMERIC_ID = re.compile(r"^\d+$")

LEVEL_COLS = (
    "dominate_required",
    "dominate_allowed",
    "non_dominate_required",
    "non_dominate_allowed",
    "non_dominate_recommended",
    "non_dominate_role_highest_level",
)
ROLE_COLS = ("dominate_role", "non_dominate_role")

DIVISION_SIG_COLS = (
    "dominate_role",
    "dominate_required",
    "dominate_allowed",
    "non_dominate_role",
    "non_dominate_required",
    "non_dominate_allowed",
    "non_dominate_recommended",
    "non_dominate_role_highest_level_points",
    "non_dominate_role_highest_level",
)

ROLE_INSERT_COLS = (
    "dancer_id",
    "dancer_name",
    "dominate_role",
    "dominate_required",
    "dominate_allowed",
    "non_dominate_role",
    "non_dominate_required",
    "non_dominate_allowed",
    "non_dominate_recommended",
    "non_dominate_role_highest_level_points",
    "non_dominate_role_highest_level",
    "valid_from",
    "valid_to",
    "run_id",
)

NAME_INSERT_COLS = ("dancer_id", "dancer_name", "valid_from", "valid_to", "run_id")


def _blank(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip()


def read_legacy_snapshots(csv_path: Path) -> pd.DataFrame:
    t0 = time.time()
    print(f"Reading {csv_path} ...", flush=True)
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    print(f"  raw rows: {len(df):,} ({time.time() - t0:.1f}s)", flush=True)

    mask = df["dancer_id"].map(lambda v: bool(NUMERIC_ID.match(str(v).strip())))
    df = df.loc[mask].copy()
    df["dancer_id"] = df["dancer_id"].astype(int)
    df["snap_date"] = pd.to_datetime(df["update_date"], errors="coerce")
    df = df.loc[df["snap_date"].notna()].copy()

    for col in LEVEL_COLS:
        if col in df.columns:
            df[col] = df[col].map(normalize_level).fillna("")
    for col in ROLE_COLS:
        if col in df.columns:
            df[col] = df[col].map(normalize_role).fillna("")
    if "dancer_name" in df.columns:
        df["dancer_name"] = df["dancer_name"].map(normalize_dancer_name).fillna("")

    for col in DIVISION_SIG_COLS:
        if col not in df.columns:
            df[col] = ""
    if "dancer_name" not in df.columns:
        df["dancer_name"] = ""

    df = df.sort_values(["dancer_id", "snap_date"])
    before = len(df)
    df = df.drop_duplicates(subset=["dancer_id", "snap_date"], keep="last")
    print(
        f"  after dancer+date dedupe: {len(df):,} (removed {before - len(df):,})",
        flush=True,
    )
    return df


def _build_intervals(df: pd.DataFrame, sig_cols: list[str]) -> pd.DataFrame:
    sig = (
        df[sig_cols]
        .fillna("")
        .astype(str)
        .apply(lambda s: s.str.strip())
        .agg("|".join, axis=1)
    )
    work = df.assign(sig=sig)
    work["prev_sig"] = work.groupby("dancer_id", sort=False)["sig"].shift()
    changes = work.loc[(work["prev_sig"].isna()) | (work["prev_sig"] != work["sig"])].copy()
    changes["next_from"] = changes.groupby("dancer_id", sort=False)["snap_date"].shift(-1)
    changes["valid_from"] = changes["snap_date"].dt.strftime("%Y-%m-%d")
    valid_to = changes["next_from"] - pd.Timedelta(days=1)
    changes["valid_to"] = valid_to.dt.strftime("%Y-%m-%d")
    changes.loc[changes["next_from"].isna(), "valid_to"] = ""
    return changes


def build_division_intervals_from_df(df: pd.DataFrame) -> pd.DataFrame:
    changes = _build_intervals(df, list(DIVISION_SIG_COLS))
    print(f"  division change snapshots: {len(changes):,}", flush=True)
    for col in DIVISION_SIG_COLS + ("dancer_name",):
        if col in changes.columns:
            changes[col] = _blank(changes[col]).replace({"": pd.NA})
    return changes


def build_name_intervals_from_df(df: pd.DataFrame) -> pd.DataFrame:
    named = df.loc[df["dancer_name"].astype(str).str.strip() != ""].copy()
    named = named.assign(_name_sig=named["dancer_name"].str.casefold())
    changes = _build_intervals(named, ["_name_sig"])
    print(f"  name change snapshots: {len(changes):,}", flush=True)
    changes["dancer_name"] = _blank(changes["dancer_name"]).replace({"": pd.NA})
    return changes.loc[changes["dancer_name"].notna()].copy()


def build_legacy_intervals(csv_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read legacy CSV once and return (division_intervals, name_intervals)."""
    df = read_legacy_snapshots(csv_path)
    return build_division_intervals_from_df(df), build_name_intervals_from_df(df)


def build_division_intervals(csv_path: Path) -> pd.DataFrame:
    return build_division_intervals_from_df(read_legacy_snapshots(csv_path))


def build_name_intervals(csv_path: Path) -> pd.DataFrame:
    return build_name_intervals_from_df(read_legacy_snapshots(csv_path))

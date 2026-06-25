#!/usr/bin/env python3
"""Build history.dancer_roles_history from changed_dancer_role_info.csv.

The SQL backfill (backfill_roles_history.sql) times out on Supabase for the
~3.4M-row legacy file. This script does the same SCD2 logic in pandas and bulk
loads via COPY.

Usage:
    python scripts/backfill_roles_history.py --csv path/to/changed_dancer_role_info.csv
    python scripts/backfill_roles_history.py --csv ... --run-id 40
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import time
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from connection import connect  # noqa: E402
from transform.normalize import normalize_level, normalize_role  # noqa: E402

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
SIG_COLS = (
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
)
INSERT_COLS = (
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


def _blank(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip()


def build_change_intervals(csv_path: Path) -> pd.DataFrame:
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

    for col in SIG_COLS:
        if col not in df.columns:
            df[col] = ""

    df = df.sort_values(["dancer_id", "snap_date"])
    before = len(df)
    df = df.drop_duplicates(subset=["dancer_id", "snap_date"], keep="last")
    print(
        f"  after dancer+date dedupe: {len(df):,} "
        f"(removed {before - len(df):,})",
        flush=True,
    )

    sig = df[list(SIG_COLS)].fillna("").astype(str).apply(lambda s: s.str.strip()).agg("|".join, axis=1)
    df = df.assign(sig=sig)
    df["prev_sig"] = df.groupby("dancer_id", sort=False)["sig"].shift()
    changes = df.loc[(df["prev_sig"].isna()) | (df["prev_sig"] != df["sig"])].copy()
    print(f"  change snapshots: {len(changes):,}", flush=True)

    changes["next_from"] = changes.groupby("dancer_id", sort=False)["snap_date"].shift(-1)
    changes["valid_from"] = changes["snap_date"].dt.strftime("%Y-%m-%d")
    valid_to = changes["next_from"] - pd.Timedelta(days=1)
    changes["valid_to"] = valid_to.dt.strftime("%Y-%m-%d")
    changes.loc[changes["next_from"].isna(), "valid_to"] = ""

    for col in SIG_COLS:
        changes[col] = _blank(changes[col]).replace({"": pd.NA})

    return changes


def copy_to_history(conn, changes: pd.DataFrame, run_id: int) -> int:
    payload = changes.assign(run_id=run_id)[list(INSERT_COLS)].copy()
    for col in payload.columns:
        if col == "run_id":
            payload[col] = payload[col].astype(int)
        else:
            payload[col] = payload[col].fillna("")

    buf = io.StringIO()
    payload.to_csv(buf, index=False, header=False)
    buf.seek(0)

    cols_sql = ", ".join(INSERT_COLS)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE history.dancer_roles_history")
        with cur.copy(
            f"COPY history.dancer_roles_history ({cols_sql}) "
            "FROM STDIN WITH (FORMAT csv, NULL '')"
        ) as copy:
            copy.write(buf.getvalue().encode("utf-8"))
    conn.commit()
    return len(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--run-id", type=int, default=None)
    args = parser.parse_args()

    if not args.csv.is_file():
        sys.exit(f"CSV not found: {args.csv}")

    changes = build_change_intervals(args.csv)

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '0'")
        conn.commit()

        run_id = args.run_id
        if run_id is None:
            with conn.cursor() as cur:
                cur.execute("SELECT COALESCE(MAX(run_id), 0) FROM history.parse_runs")
                run_id = int(cur.fetchone()[0])
        if run_id <= 0:
            sys.exit("No parse_runs row found — pass --run-id from backfill.py")

        print(f"Loading {len(changes):,} intervals into history (run_id={run_id}) ...", flush=True)
        t0 = time.time()
        count = copy_to_history(conn, changes, run_id)
        print(f"Done: {count:,} rows in {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()

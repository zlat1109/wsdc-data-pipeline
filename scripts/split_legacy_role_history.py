#!/usr/bin/env python3
"""Split legacy changed_dancer_role_info.csv into division + name SCD2 tables.

Usage:
    python scripts/split_legacy_role_history.py --csv data/changed_dancer_role_info.csv --dry-run
    python scripts/split_legacy_role_history.py --csv ... --apply [--run-id N]
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from connection import connect  # noqa: E402
from transform.history.legacy_role_split import (  # noqa: E402
    NAME_INSERT_COLS,
    ROLE_INSERT_COLS,
    build_legacy_intervals,
)


def _copy_df(conn, table: str, columns: tuple[str, ...], df, run_id: int) -> int:
    payload = df.assign(run_id=run_id)[list(columns)].copy()
    for col in payload.columns:
        if col == "run_id":
            payload[col] = payload[col].astype(int)
        else:
            payload[col] = payload[col].fillna("")

    buf = io.StringIO()
    payload.to_csv(buf, index=False, header=False)
    buf.seek(0)

    cols_sql = ", ".join(columns)
    with conn.cursor() as cur:
        cur.execute(f"TRUNCATE {table}")
        with cur.copy(
            f"COPY {table} ({cols_sql}) FROM STDIN WITH (FORMAT csv, NULL '')"
        ) as copy:
            copy.write(buf.getvalue().encode("utf-8"))
    return len(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--run-id", type=int, default=None)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not args.csv.is_file():
        sys.exit(f"CSV not found: {args.csv}")

    division, names = build_legacy_intervals(args.csv)
    print(f"\nDivision intervals: {len(division):,}")
    print(f"Name intervals: {len(names):,}")

    if args.dry_run:
        print("\nDry run — no DB changes.")
        return

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
            sys.exit("No parse_runs row found — pass --run-id")

        role_count = _copy_df(
            conn,
            "history.dancer_roles_history",
            ROLE_INSERT_COLS,
            division,
            run_id,
        )
        name_count = _copy_df(
            conn,
            "history.dancer_names_history",
            NAME_INSERT_COLS,
            names,
            run_id,
        )
        conn.commit()

    print(f"\nLoaded {role_count:,} role intervals and {name_count:,} name intervals (run_id={run_id}).")


if __name__ == "__main__":
    main()

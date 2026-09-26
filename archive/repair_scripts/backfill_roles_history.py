#!/usr/bin/env python3
"""Build history.dancer_roles_history from changed_dancer_role_info.csv (divisions only).

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
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from connection import connect  # noqa: E402
from transform.history.legacy_role_split import (  # noqa: E402
    ROLE_INSERT_COLS,
    build_division_intervals,
)


def copy_to_history(conn, changes, run_id: int) -> int:
    payload = changes.assign(run_id=run_id)[list(ROLE_INSERT_COLS)].copy()
    for col in payload.columns:
        if col == "run_id":
            payload[col] = payload[col].astype(int)
        else:
            payload[col] = payload[col].fillna("")

    buf = io.StringIO()
    payload.to_csv(buf, index=False, header=False)
    buf.seek(0)

    cols_sql = ", ".join(ROLE_INSERT_COLS)
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

    changes = build_division_intervals(args.csv)

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

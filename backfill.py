#!/usr/bin/env python3
"""Initial load: CSV files -> staging -> core + points history from changed_*.csv.

Usage:
    python backfill.py
    python backfill.py --data-dir "/path/to/WSDC Points"
    python backfill.py --skip-points-history
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"

sys.path.insert(0, str(PROJECT_ROOT / "db"))

from connection import connect  # noqa: E402
from enrich_known_events import enrich_core_known_events  # noqa: E402
from staging_loader import load_staging_from_dir  # noqa: E402
from watermark import refresh_watermark  # noqa: E402


def read_sql(name: str) -> str:
    return (PROJECT_ROOT / "db" / "sql" / name).read_text(encoding="utf-8")


def start_run(cur, source: str) -> int:
    cur.execute(
        """
        INSERT INTO history.parse_runs (source, status)
        VALUES (%s, 'running')
        RETURNING run_id
        """,
        (source,),
    )
    return cur.fetchone()[0]


def finish_run(cur, run_id: int, counts: dict[str, int], conn) -> None:
    cur.execute(
        """
        UPDATE history.parse_runs
        SET finished_at = %s,
            status = 'success',
            rows_results = %s,
            rows_points = %s
        WHERE run_id = %s
        """,
        (
            datetime.now(timezone.utc),
            counts.get("dancers_results_info.csv"),
            counts.get("dancers_points_info.csv"),
            run_id,
        ),
    )
    conn.commit()
    wm = refresh_watermark(conn, run_id)
    print(f"Watermark updated to {wm}")


def print_core_counts(cur) -> None:
    tables = [
        "core.dancers",
        "core.locations",
        "core.events",
        "core.event_instances",
        "core.dancer_points",
        "core.dancer_roles",
        "core.results",
        "history.dancer_points_history",
        "history.dancer_roles_history",
    ]
    print("\nRow counts in Supabase:")
    for table in tables:
        cur.execute(f"SELECT count(*) FROM {table}")
        print(f"  {table}: {cur.fetchone()[0]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory with WSDC CSV files",
    )
    parser.add_argument(
        "--skip-points-history",
        action="store_true",
        help="Skip loading history from changed_* points CSV",
    )
    parser.add_argument(
        "--roles-only",
        action="store_true",
        help="Only build role history from changed_dancer_role_info.csv (skip staging/core)",
    )
    args = parser.parse_args()

    if args.roles_only:
        roles_changed = args.data_dir / "changed_dancer_role_info.csv"
        if not roles_changed.exists():
            sys.exit(f"Missing {roles_changed}")
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SET statement_timeout = '0'")
                cur.execute("SELECT COALESCE(MAX(run_id), 0) FROM history.parse_runs")
                run_id = int(cur.fetchone()[0])
            conn.commit()
            if run_id <= 0:
                sys.exit("No parse_runs row — run full backfill first")
            print(f"Role-history only (run_id={run_id}) ...")
            subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "scripts" / "backfill_roles_history.py"),
                    "--csv",
                    str(roles_changed),
                    "--run-id",
                    str(run_id),
                ],
                cwd=PROJECT_ROOT,
                check=True,
            )
        print("\nRole history backfill complete.")
        return

    print(f"Data directory: {args.data_dir}")

    with connect() as conn:
        with conn.cursor() as cur:
            # Legacy changed_dancer_role_info can be 3M+ rows; disable statement cap.
            cur.execute("SET statement_timeout = '0'")
        conn.commit()

        print("Loading CSVs into staging ...")
        staging_counts = load_staging_from_dir(conn, args.data_dir)
        for name, count in staging_counts.items():
            print(f"  {name}: {count} rows")

        with conn.cursor() as cur:
            run_id = start_run(cur, "backfill")
            conn.commit()
            print(f"parse_run id: {run_id}")

            print("Promoting staging -> core ...")
            cur.execute(read_sql("promote_core.sql"))
            enrich_core_known_events(conn)

            if not args.skip_points_history:
                changed_path = args.data_dir / "changed_dancers_points_info.csv"
                if not changed_path.exists():
                    changed_path = args.data_dir / "changed_dancer_points_info.csv"
                if changed_path.exists():
                    print(f"Building points history from {changed_path.name} ...")
                    cur.execute("TRUNCATE history.dancer_points_history")
                    cur.execute(
                        read_sql("backfill_points_history.sql"),
                        {"run_id": run_id},
                    )
                else:
                    print("No changed_* points CSV found — skipping points history")

                roles_changed = args.data_dir / "changed_dancer_role_info.csv"
                if roles_changed.exists():
                    print(
                        f"Building role history from {roles_changed.name} "
                        "(pandas — SQL times out on 3M+ rows) ..."
                    )
                    conn.commit()
                    subprocess.run(
                        [
                            sys.executable,
                            str(PROJECT_ROOT / "scripts" / "backfill_roles_history.py"),
                            "--csv",
                            str(roles_changed),
                            "--run-id",
                            str(run_id),
                        ],
                        cwd=PROJECT_ROOT,
                        check=True,
                    )
                    cur.execute("SELECT count(*) FROM history.dancer_roles_history")
                    print(f"  role history rows: {cur.fetchone()[0]}")
                else:
                    print("No changed_dancer_role_info.csv found — skipping role history")

            finish_run(cur, run_id, staging_counts, conn)

            print_core_counts(cur)

    print("\nBackfill complete.")


if __name__ == "__main__":
    main()

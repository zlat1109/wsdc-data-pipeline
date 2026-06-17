#!/usr/bin/env python3
"""Weekly load: CSV -> staging -> history diff -> core refresh.

Usage:
    python load.py --data-dir "/path/to/WSDC Points"
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"

sys.path.insert(0, str(PROJECT_ROOT / "db"))

from connection import connect  # noqa: E402
from build_event_catalog import rebuild_event_catalog  # noqa: E402
from enrich_known_events import enrich_core_known_events  # noqa: E402
from staging_loader import load_staging_from_dir  # noqa: E402
from watermark import refresh_watermark  # noqa: E402


def read_sql(name: str) -> str:
    return (PROJECT_ROOT / "db" / "sql" / name).read_text(encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument(
        "--source",
        default="local",
        choices=["local", "github-actions"],
    )
    args = parser.parse_args()

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '600s'")

        staging_counts = load_staging_from_dir(conn, args.data_dir)

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO history.parse_runs (source, status)
                VALUES (%s, 'running')
                RETURNING run_id
                """,
                (args.source,),
            )
            run_id = cur.fetchone()[0]

            cur.execute(
                read_sql("record_weekly_points_history.sql"),
                {"run_id": run_id},
            )
            cur.execute(read_sql("promote_core.sql"))
            enrich_core_known_events(conn)
            catalog_count, edition_count = rebuild_event_catalog(conn)
            cur.execute("ANALYZE core.results, core.event_editions, core.event_catalog")

            cur.execute(
                """
                UPDATE history.parse_runs
                SET finished_at = %s, status = 'success',
                    rows_results = %s, rows_points = %s
                WHERE run_id = %s
                """,
                (
                    datetime.now(timezone.utc),
                    staging_counts.get("dancers_results_info.csv"),
                    staging_counts.get("dancers_points_info.csv"),
                    run_id,
                ),
            )
            conn.commit()
            wm = refresh_watermark(conn, run_id)
            print(f"Watermark updated to {wm}")

    print(f"Load complete (run_id={run_id}).")
    print(f"Event catalog: {catalog_count} events, {edition_count} editions.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Close stuck history.parse_runs rows.

Usage:
    python scripts/close_parse_runs.py --dry-run
    python scripts/close_parse_runs.py --apply
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from connection import connect  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT run_id, source, status, started_at, finished_at
                FROM history.parse_runs
                WHERE status = 'running'
                ORDER BY run_id
                """
            )
            rows = cur.fetchall()

        print(f"Stuck running parse_runs: {len(rows)}")
        for run_id, source, status, started_at, finished_at in rows:
            print(f"  run_id={run_id} source={source} started={started_at} finished={finished_at}")

        if args.dry_run or not rows:
            if args.dry_run:
                print("\nDry run — no changes applied.")
            return

        now = datetime.now(timezone.utc)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE history.parse_runs
                SET status = 'success',
                    finished_at = coalesce(finished_at, %s)
                WHERE status = 'running'
                  AND (finished_at IS NOT NULL OR source = 'github-actions')
                """,
                (now,),
            )
            closed_partial = cur.rowcount
            cur.execute(
                """
                UPDATE history.parse_runs
                SET status = 'failed',
                    finished_at = coalesce(finished_at, %s)
                WHERE status = 'running'
                  AND source = 'backfill'
                  AND run_id IN (1, 2)
                """,
                (now,),
            )
            cancelled = cur.rowcount
        conn.commit()

    print(f"\nClosed as success: {closed_partial}; cancelled ancient backfill: {cancelled}")


if __name__ == "__main__":
    main()

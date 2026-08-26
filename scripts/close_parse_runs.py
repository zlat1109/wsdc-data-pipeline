#!/usr/bin/env python3
"""Close stuck history.parse_runs rows.

Usage:
    python scripts/close_parse_runs.py --dry-run
    python scripts/close_parse_runs.py --apply
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from connection import connect  # noqa: E402

# Runs older than this are treated as zombies for *manual* close / listing.
STUCK_PARSE_MIN_AGE_MINUTES = int(os.getenv("STUCK_PARSE_MIN_AGE_MINUTES", "90"))
# Auto-close must exceed a typical full-parse (~2–3h). Do not use the 90m in-flight window.
AUTO_CLOSE_STUCK_PARSE_MIN_AGE_MINUTES = int(
    os.getenv("AUTO_CLOSE_STUCK_PARSE_MIN_AGE_MINUTES", "240")
)


def find_stuck_running_parse_runs(
    conn,
    *,
    min_age_minutes: int | None = None,
) -> list[dict[str, Any]]:
    """Return status=running rows older than min_age (UTC)."""
    age = min_age_minutes if min_age_minutes is not None else STUCK_PARSE_MIN_AGE_MINUTES
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=age)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT run_id, source, status, started_at, finished_at
            FROM history.parse_runs
            WHERE status = 'running'
              AND started_at < %s
            ORDER BY run_id
            """,
            (cutoff,),
        )
        rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for run_id, source, status, started_at, finished_at in rows:
        age_min = None
        if started_at is not None:
            started = started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            age_min = int((now - started).total_seconds() // 60)
        out.append(
            {
                "run_id": int(run_id),
                "source": source,
                "status": status,
                "started_at": started_at.isoformat() if started_at else None,
                "finished_at": finished_at.isoformat() if finished_at else None,
                "age_minutes": age_min,
            }
        )
    return out


def close_stuck_running_parse_runs(
    conn,
    *,
    min_age_minutes: int | None = None,
    dry_run: bool = False,
    probe_zombies_only: bool = False,
) -> dict[str, Any]:
    """Mark stuck running parse_runs as failed. Returns summary for Telegram/probe.

    ``probe_zombies_only``: only close runs that finished the probe but never got a
    successful load (``finished_at IS NOT NULL``). Safer for short thresholds.
    """
    age = (
        min_age_minutes
        if min_age_minutes is not None
        else STUCK_PARSE_MIN_AGE_MINUTES
    )
    stuck = find_stuck_running_parse_runs(conn, min_age_minutes=age)
    if probe_zombies_only:
        stuck = [s for s in stuck if s.get("finished_at")]
    summary: dict[str, Any] = {
        "stuck_count": len(stuck),
        "closed_count": 0,
        "dry_run": dry_run,
        "min_age_minutes": age,
        "probe_zombies_only": probe_zombies_only,
        "stuck": stuck[:20],
    }
    if dry_run or not stuck:
        return summary

    now = datetime.now(timezone.utc)
    run_ids = [s["run_id"] for s in stuck]
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE history.parse_runs
            SET status = 'failed',
                finished_at = coalesce(finished_at, %s)
            WHERE status = 'running'
              AND run_id = ANY(%s)
            """,
            (now, run_ids),
        )
        summary["closed_count"] = int(cur.rowcount or 0)
    conn.commit()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--min-age-minutes",
        type=int,
        default=STUCK_PARSE_MIN_AGE_MINUTES,
        help="Only close running rows older than this many minutes (default %(default)s)",
    )
    args = parser.parse_args()

    with connect() as conn:
        # Legacy: also list ALL running (for operator visibility), then close by age.
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT run_id, source, status, started_at, finished_at
                FROM history.parse_runs
                WHERE status = 'running'
                ORDER BY run_id
                """
            )
            all_running = cur.fetchall()
        print(f"Running parse_runs (any age): {len(all_running)}")
        for run_id, source, status, started_at, finished_at in all_running:
            print(
                f"  run_id={run_id} source={source} started={started_at} "
                f"finished={finished_at}"
            )

        summary = close_stuck_running_parse_runs(
            conn,
            min_age_minutes=args.min_age_minutes,
            dry_run=args.dry_run,
        )
        print(
            f"\nStuck older than {summary['min_age_minutes']}m: "
            f"{summary['stuck_count']}"
        )
        if args.dry_run:
            print("Dry run — no changes applied.")
            print("To close: python scripts/close_parse_runs.py --apply")
            return
        print(f"Closed as failed: {summary['closed_count']}")


if __name__ == "__main__":
    main()

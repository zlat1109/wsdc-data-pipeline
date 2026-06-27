#!/usr/bin/env python3
"""Reconcile open history.dancer_points_history with core.dancer_points snapshot.

Usage:
    python scripts/reconcile_points_history.py --dry-run
    python scripts/reconcile_points_history.py --apply
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from connection import connect  # noqa: E402

STALE_OPEN_SQL = """
SELECT h.dancer_id, h.role, h.dance, h.level, h.total_points AS hist_points,
       p.total_points AS core_points
FROM history.dancer_points_history h
LEFT JOIN core.dancer_points p
  ON p.dancer_id = h.dancer_id AND p.role = h.role
  AND p.dance = h.dance AND p.level = h.level
WHERE h.valid_to IS NULL
  AND (p.dancer_id IS NULL OR p.total_points IS DISTINCT FROM h.total_points)
"""

MISSING_OPEN_SQL = """
SELECT p.dancer_id, p.role, p.dance, p.level, p.total_points, p.update_date
FROM core.dancer_points p
WHERE NOT EXISTS (
    SELECT 1 FROM history.dancer_points_history h
    WHERE h.valid_to IS NULL
      AND h.dancer_id = p.dancer_id AND h.role = p.role
      AND h.dance = p.dance AND h.level = p.level
      AND h.total_points = p.total_points
)
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    today = date.today()

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(STALE_OPEN_SQL)
            stale = cur.fetchall()
            cur.execute(MISSING_OPEN_SQL)
            missing = cur.fetchall()
            cur.execute(
                "SELECT COALESCE(MAX(run_id), 1) FROM history.parse_runs WHERE status = 'success'"
            )
            run_id = int(cur.fetchone()[0])

        print(f"Stale open intervals to close: {len(stale)}")
        print(f"Missing open intervals to insert: {len(missing)}")

        if args.dry_run:
            print("\nDry run — no changes applied.")
            return

        with conn.cursor() as cur:
            for dancer_id, role, dance, level, _, _ in stale:
                cur.execute(
                    """
                    UPDATE history.dancer_points_history
                    SET valid_to = %s
                    WHERE dancer_id = %s AND role = %s AND dance = %s AND level = %s
                      AND valid_to IS NULL
                    """,
                    (today, dancer_id, role, dance, level),
                )

            for dancer_id, role, dance, level, total_points, update_date in missing:
                valid_from = update_date or today
                cur.execute(
                    """
                    INSERT INTO history.dancer_points_history (
                        dancer_id, role, dance, level, total_points, valid_from, valid_to, run_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, NULL, %s)
                    """,
                    (dancer_id, role, dance, level, total_points, valid_from, run_id),
                )

            cur.execute(
                """
                SELECT count(*) FROM history.dancer_points_history h
                WHERE h.valid_to IS NULL AND NOT EXISTS (
                    SELECT 1 FROM core.dancer_points p
                    WHERE p.dancer_id = h.dancer_id AND p.role = h.role
                      AND p.dance = h.dance AND p.level = h.level
                      AND p.total_points = h.total_points
                )
                """
            )
            remaining = int(cur.fetchone()[0])
        conn.commit()

    print(f"\nReconcile complete. Remaining drift: {remaining}")


if __name__ == "__main__":
    main()

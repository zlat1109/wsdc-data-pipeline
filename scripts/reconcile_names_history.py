#!/usr/bin/env python3
"""Reconcile open history.dancer_names_history with core.dancers.dancer_name.

Usage:
    python scripts/reconcile_names_history.py --dry-run
    python scripts/reconcile_names_history.py --apply
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from connection import connect  # noqa: E402

STALE_COUNT_SQL = """
SELECT count(*)
FROM history.dancer_names_history h
LEFT JOIN core.dancers d ON d.dancer_id = h.dancer_id
WHERE h.valid_to IS NULL
  AND (d.dancer_id IS NULL OR d.dancer_name IS DISTINCT FROM h.dancer_name)
"""

MISSING_COUNT_SQL = """
SELECT count(*)
FROM core.dancers d
WHERE d.dancer_name IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM history.dancer_names_history h
    WHERE h.valid_to IS NULL
      AND h.dancer_id = d.dancer_id
      AND h.dancer_name = d.dancer_name
  )
"""

CLOSE_STALE_SQL = """
UPDATE history.dancer_names_history h
SET valid_to = %(today)s
FROM core.dancers d
WHERE h.valid_to IS NULL
  AND h.dancer_id = d.dancer_id
  AND d.dancer_name IS DISTINCT FROM h.dancer_name
"""

CLOSE_ORPHAN_SQL = """
UPDATE history.dancer_names_history h
SET valid_to = %(today)s
WHERE h.valid_to IS NULL
  AND NOT EXISTS (SELECT 1 FROM core.dancers d WHERE d.dancer_id = h.dancer_id)
"""

INSERT_MISSING_SQL = """
INSERT INTO history.dancer_names_history (
    dancer_id, dancer_name, valid_from, valid_to, run_id
)
SELECT
    d.dancer_id,
    d.dancer_name,
    %(today)s,
    NULL,
    %(run_id)s
FROM core.dancers d
WHERE d.dancer_name IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM history.dancer_names_history h
    WHERE h.valid_to IS NULL
      AND h.dancer_id = d.dancer_id
      AND h.dancer_name = d.dancer_name
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
            cur.execute(STALE_COUNT_SQL)
            stale = int(cur.fetchone()[0])
            cur.execute(MISSING_COUNT_SQL)
            missing = int(cur.fetchone()[0])

        print(f"Stale open name intervals to close: {stale}")
        print(f"Missing open name intervals to insert: {missing}")

        if args.dry_run:
            print("\nDry run — no changes applied.")
            return

        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(MAX(run_id), 1) FROM history.parse_runs WHERE status = 'success'"
            )
            run_id = int(cur.fetchone()[0])
            cur.execute(CLOSE_STALE_SQL, {"today": today})
            closed_stale = cur.rowcount
            cur.execute(CLOSE_ORPHAN_SQL, {"today": today})
            closed_orphan = cur.rowcount
            cur.execute(INSERT_MISSING_SQL, {"today": today, "run_id": run_id})
            inserted = cur.rowcount
            cur.execute(STALE_COUNT_SQL)
            remaining = int(cur.fetchone()[0])
        conn.commit()

    print(
        f"\nReconcile complete. Closed {closed_stale + closed_orphan:,} "
        f"(stale={closed_stale:,}, orphan={closed_orphan:,}), "
        f"inserted {inserted:,}, remaining drift {remaining:,}."
    )


if __name__ == "__main__":
    main()

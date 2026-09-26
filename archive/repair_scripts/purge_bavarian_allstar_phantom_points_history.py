#!/usr/bin/env python3
"""Remove phantom Bavarian Open 2026 All-Star opposite-role points history.

After the role-swap repair, core.dancer_points correctly dropped the wrong-role
All-Star buckets, but SCD2 only closed those intervals. Tableau's
changed_dancer_points_info uses the latest update_date per (dancer, role, level),
so a closed Follower=8 row still looks like current points (e.g. Joshua Schubert).

These one-day intervals (2026-09-14 → 2026-09-15) were never real — delete them.

Usage:
    python scripts/purge_bavarian_allstar_phantom_points_history.py --dry-run
    python scripts/purge_bavarian_allstar_phantom_points_history.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from connection import connect  # noqa: E402

# Dancers whose All-Star role was flipped in repair_bavarian_allstar_roles_2026.
FLIPPED_DANCER_IDS = (
    9062,
    9282,
    10951,
    12424,
    13295,
    14183,
    14186,
    14614,
    17254,
    17339,
    17340,
    17823,
    18932,
    19457,
    20300,
    20585,
)

SELECT_SQL = """
SELECT h.dancer_id, d.dancer_name, h.role, h.total_points, h.valid_from, h.valid_to
FROM history.dancer_points_history h
JOIN core.dancers d ON d.dancer_id = h.dancer_id
WHERE h.dancer_id = ANY(%s)
  AND h.level = 'All-Star'
  AND h.dance = 'West Coast Swing'
  AND h.valid_from = DATE '2026-09-14'
  AND h.valid_to = DATE '2026-09-15'
  AND NOT EXISTS (
      SELECT 1
      FROM core.dancer_points p
      WHERE p.dancer_id = h.dancer_id
        AND p.role = h.role
        AND p.dance = h.dance
        AND p.level = h.level
  )
ORDER BY d.dancer_name, h.role
"""

DELETE_SQL = """
DELETE FROM history.dancer_points_history h
WHERE h.dancer_id = ANY(%s)
  AND h.level = 'All-Star'
  AND h.dance = 'West Coast Swing'
  AND h.valid_from = DATE '2026-09-14'
  AND h.valid_to = DATE '2026-09-15'
  AND NOT EXISTS (
      SELECT 1
      FROM core.dancer_points p
      WHERE p.dancer_id = h.dancer_id
        AND p.role = h.role
        AND p.dance = h.dance
        AND p.level = h.level
  )
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.dry_run == args.apply:
        print("Specify exactly one of --dry-run or --apply")
        return 2

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_SQL, (list(FLIPPED_DANCER_IDS),))
            rows = cur.fetchall()
            print(f"Phantom All-Star history intervals to purge: {len(rows)}")
            for dancer_id, name, role, points, valid_from, valid_to in rows:
                print(
                    f"  {name} ({dancer_id}) {role}={points} "
                    f"[{valid_from} → {valid_to}]"
                )

            if args.dry_run:
                print("dry-run only — no writes")
                return 0

            cur.execute(DELETE_SQL, (list(FLIPPED_DANCER_IDS),))
            print(f"deleted {cur.rowcount} history rows")
            conn.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

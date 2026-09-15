#!/usr/bin/env python3
"""Repair Bavarian Open 2026 All-Star swapped leader/follower roles in Supabase.

Flips core.results.role where listed role contradicts dominate_role, then moves
the same points between Leader/Follower buckets in core.dancer_points.

Usage:
    python scripts/repair_bavarian_allstar_roles_2026.py --dry-run
    python scripts/repair_bavarian_allstar_roles_2026.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from connection import connect  # noqa: E402
from transform.result_role_corrections import (  # noqa: E402
    BAVARIAN_OPEN_ALLSTAR_ROLE_SWAP_2026,
    _canon_role,
)

EVENT_ID = BAVARIAN_OPEN_ALLSTAR_ROLE_SWAP_2026["event_id"]
EVENT_YEAR = BAVARIAN_OPEN_ALLSTAR_ROLE_SWAP_2026["event_year"]

SELECT_MISMATCH_SQL = """
SELECT
    r.result_id,
    r.dancer_id,
    d.dancer_name,
    r.role AS listed_role,
    dr.dominate_role,
    r.result_standardized,
    r.points
FROM core.results r
JOIN core.dancers d ON d.dancer_id = r.dancer_id
LEFT JOIN core.dancer_roles dr ON dr.dancer_id = r.dancer_id
WHERE r.event_id = %s
  AND r.event_year = %s
  AND lower(replace(r.division, ' ', '')) IN ('all-star', 'allstars', 'als')
  AND dr.dominate_role IS NOT NULL
  AND lower(r.role) <> lower(dr.dominate_role)
ORDER BY
    CASE WHEN r.result_standardized ~ '^[0-9]+$' THEN r.result_standardized::int ELSE 900 END,
    r.role,
    r.dancer_id
"""


def _fetch_mismatches(cur) -> list[dict]:
    cur.execute(SELECT_MISMATCH_SQL, (EVENT_ID, EVENT_YEAR))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _move_points(cur, dancer_id: int, from_role: str, to_role: str, points: int) -> None:
    if points <= 0:
        return
    dance = "West Coast Swing"
    level = "All-Star"

    cur.execute(
        """
        UPDATE core.dancer_points
        SET total_points = total_points - %s
        WHERE dancer_id = %s AND role = %s AND dance = %s AND level = %s
        RETURNING total_points
        """,
        (points, dancer_id, from_role, dance, level),
    )
    row = cur.fetchone()
    if row is not None and row[0] <= 0:
        cur.execute(
            """
            DELETE FROM core.dancer_points
            WHERE dancer_id = %s AND role = %s AND dance = %s AND level = %s
            """,
            (dancer_id, from_role, dance, level),
        )

    cur.execute(
        """
        INSERT INTO core.dancer_points (dancer_id, role, dance, level, total_points, update_date)
        VALUES (%s, %s, %s, %s, %s, CURRENT_DATE)
        ON CONFLICT (dancer_id, role, dance, level) DO UPDATE
        SET total_points = core.dancer_points.total_points + EXCLUDED.total_points,
            update_date = EXCLUDED.update_date
        """,
        (dancer_id, to_role, dance, level, points),
    )


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
            mismatches = _fetch_mismatches(cur)
            print(
                f"Bavarian Open {EVENT_YEAR} All-Star role mismatches "
                f"(event_id={EVENT_ID}): {len(mismatches)}"
            )
            for row in mismatches:
                print(
                    f"  result_id={row['result_id']} place={row['result_standardized']} "
                    f"{row['dancer_name']} ({row['dancer_id']}): "
                    f"{row['listed_role']} → {row['dominate_role']} "
                    f"pts={row['points']}"
                )

            if args.dry_run:
                print("dry-run only — no writes")
                return 0

            for row in mismatches:
                listed = _canon_role(row["listed_role"])
                target = _canon_role(row["dominate_role"])
                if not listed or not target or listed == target:
                    continue
                cur.execute(
                    "UPDATE core.results SET role = %s WHERE result_id = %s",
                    (target, row["result_id"]),
                )
                _move_points(
                    cur,
                    int(row["dancer_id"]),
                    listed,
                    target,
                    int(row["points"] or 0),
                )

            conn.commit()
            print(f"applied {len(mismatches)} result role flips + point transfers")

            remaining = _fetch_mismatches(cur)
            print(f"remaining mismatches: {len(remaining)}")
            if remaining:
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

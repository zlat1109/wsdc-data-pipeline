#!/usr/bin/env python3
"""Recompute non-dominate highest level/points from core.dancer_points.

After Bavarian Open All-Star role repair, WSDC role summaries still advertised
phantom NDR All-Star totals (e.g. Joshua Schubert Follower All-Star = 8). The
Dancer Profile secondary bar reads dancer_role_info, not dancers_points_info.

Usage:
    python scripts/repair_ndr_highest_from_points.py --dry-run
    python scripts/repair_ndr_highest_from_points.py --apply
    python scripts/repair_ndr_highest_from_points.py --apply --dancer-ids 13295,14614
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from connection import connect  # noqa: E402

# Skill-ladder levels only (exclude age/special tracks for "highest").
SKILL_LEVELS = (
    "Newcomer",
    "Novice",
    "Intermediate",
    "Advanced",
    "All-Star",
    "Champion",
    "Master",
)

# Default: dancers flipped in Bavarian Open 2026 All-Star repair.
DEFAULT_DANCER_IDS = (
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
SELECT
    r.dancer_id,
    d.dancer_name,
    r.non_dominate_role,
    r.non_dominate_role_highest_level AS old_level,
    r.non_dominate_role_highest_level_points AS old_points,
    (
        SELECT p.level
        FROM core.dancer_points p
        JOIN core.levels l ON l.level = p.level
        WHERE p.dancer_id = r.dancer_id
          AND p.role = r.non_dominate_role
          AND p.level = ANY(%s)
        ORDER BY l.sort_order DESC, p.total_points DESC
        LIMIT 1
    ) AS new_level,
    (
        SELECT p.total_points::text
        FROM core.dancer_points p
        JOIN core.levels l ON l.level = p.level
        WHERE p.dancer_id = r.dancer_id
          AND p.role = r.non_dominate_role
          AND p.level = ANY(%s)
        ORDER BY l.sort_order DESC, p.total_points DESC
        LIMIT 1
    ) AS new_points
FROM core.dancer_roles r
JOIN core.dancers d ON d.dancer_id = r.dancer_id
WHERE r.dancer_id = ANY(%s)
ORDER BY d.dancer_name
"""

UPDATE_SQL = """
UPDATE core.dancer_roles
SET non_dominate_role_highest_level = %s,
    non_dominate_role_highest_level_points = %s,
    update_date = CURRENT_DATE
WHERE dancer_id = %s
  AND (
      non_dominate_role_highest_level IS DISTINCT FROM %s
      OR non_dominate_role_highest_level_points IS DISTINCT FROM %s
  )
"""


def _norm_level(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    # WSDC / legacy exports sometimes use "All Star".
    if text.lower().replace("-", " ") == "all star":
        return "All-Star"
    return text


def _norm_points(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--dancer-ids",
        default="",
        help="Comma-separated dancer_ids (default: Bavarian All-Star flip set)",
    )
    args = parser.parse_args()
    if args.dry_run == args.apply:
        print("Specify exactly one of --dry-run or --apply")
        return 2

    if args.dancer_ids.strip():
        dancer_ids = [int(x.strip()) for x in args.dancer_ids.split(",") if x.strip()]
    else:
        dancer_ids = list(DEFAULT_DANCER_IDS)

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_SQL, (list(SKILL_LEVELS), list(SKILL_LEVELS), dancer_ids))
            rows = cur.fetchall()
            changes = []
            for (
                dancer_id,
                name,
                ndr_role,
                old_level,
                old_points,
                new_level,
                new_points,
            ) in rows:
                old_l = _norm_level(old_level)
                old_p = _norm_points(old_points)
                new_l = _norm_level(new_level)
                new_p = _norm_points(new_points)
                if old_l == new_l and old_p == new_p:
                    continue
                changes.append(
                    (dancer_id, name, ndr_role, old_l, old_p, new_l, new_p)
                )

            print(f"NDR highest mismatches to fix: {len(changes)}")
            for dancer_id, name, ndr_role, old_l, old_p, new_l, new_p in changes:
                print(
                    f"  {name} ({dancer_id}) {ndr_role}: "
                    f"{old_l}={old_p} → {new_l}={new_p}"
                )

            if args.dry_run:
                print("dry-run only — no writes")
                return 0

            updated = 0
            for dancer_id, _name, _role, _ol, _op, new_l, new_p in changes:
                cur.execute(
                    UPDATE_SQL,
                    (new_l, new_p, dancer_id, new_l, new_p),
                )
                updated += cur.rowcount
            conn.commit()
            print(f"updated {updated} dancer_roles rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

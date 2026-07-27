#!/usr/bin/env python3
"""Load WSDC tier rules from transform/knowledge/tier_rules.py into Supabase.

Usage:
    python scripts/load_tier_rules.py
    python scripts/load_tier_rules.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from connection import connect  # noqa: E402
from transform.knowledge.tier_rules import (  # noqa: E402
    RULES_EDITIONS,
    TIER_DEFINITIONS,
    TIER_POINTS,
)


def load_tier_rules(conn, *, dry_run: bool = False) -> dict[str, int]:
    editions = list(RULES_EDITIONS)
    definitions = list(TIER_DEFINITIONS)
    points = list(TIER_POINTS)

    if dry_run:
        return {
            "editions": len(editions),
            "definitions": len(definitions),
            "points": len(points),
        }

    with conn.cursor() as cur:
        # Delete children first (FK), then editions — full replace is intentional.
        cur.execute("DELETE FROM core.tier_points")
        cur.execute("DELETE FROM core.tier_definitions")
        cur.execute("UPDATE core.rules_editions SET inherits_from = NULL")
        cur.execute("DELETE FROM core.rules_editions")

        # Insert parents before children that reference inherits_from.
        # Two-pass: rows without inherits_from first, then the rest.
        roots = [e for e in editions if e.inherits_from is None]
        children = [e for e in editions if e.inherits_from is not None]
        for batch in (roots, children):
            for e in batch:
                cur.execute(
                    """
                    INSERT INTO core.rules_editions (
                        rules_version, valid_from, valid_to, tier_basis,
                        min_role_competitors, points_depth, inherits_from,
                        source_url, source, notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        e.rules_version,
                        e.valid_from,
                        e.valid_to,
                        e.tier_basis,
                        e.min_role_competitors,
                        e.points_depth,
                        e.inherits_from,
                        e.source_url,
                        e.source,
                        e.notes or None,
                    ),
                )

        for d in definitions:
            cur.execute(
                """
                INSERT INTO core.tier_definitions (
                    rules_version, tier, min_competitors, max_competitors,
                    prelim_rounds, finalist_points, source
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    d.rules_version,
                    d.tier,
                    d.min_competitors,
                    d.max_competitors,
                    d.prelim_rounds,
                    d.finalist_points,
                    d.source,
                ),
            )

        for p in points:
            cur.execute(
                """
                INSERT INTO core.tier_points (
                    rules_version, tier, placement, points, source
                ) VALUES (%s, %s, %s, %s, %s)
                """,
                (p.rules_version, p.tier, p.placement, p.points, p.source),
            )

    conn.commit()
    return {
        "editions": len(editions),
        "definitions": len(definitions),
        "points": len(points),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        counts = load_tier_rules(None, dry_run=True)
        print(f"Dry-run: {counts}")
        return 0

    with connect() as conn:
        counts = load_tier_rules(conn)
    print(
        f"Loaded tier rules: editions={counts['editions']} "
        f"definitions={counts['definitions']} points={counts['points']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

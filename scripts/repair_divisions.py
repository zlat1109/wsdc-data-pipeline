#!/usr/bin/env python3
"""Repair non-canonical division values in core.results.

Usage:
    python scripts/repair_divisions.py --dry-run
    python scripts/repair_divisions.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from connection import connect  # noqa: E402
from transform.normalize import CANONICAL_LEVELS, normalize_division  # noqa: E402


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
                SELECT division, count(*)::int
                FROM core.results
                WHERE division IS NOT NULL
                GROUP BY division
                ORDER BY count(*) DESC
                """
            )
            rows = cur.fetchall()

        changes: list[tuple[str, str, int]] = []
        for division, count in rows:
            normalized = normalize_division(division)
            if normalized and normalized != division and normalized in CANONICAL_LEVELS:
                changes.append((division, normalized, count))

        total = sum(c[2] for c in changes)
        print(f"Division repairs: {len(changes)} distinct values, {total} rows")
        for old, new, count in changes:
            print(f"  {old!r} -> {new!r}: {count}")

        if not changes:
            return
        if args.dry_run:
            print("\nDry run — no changes applied.")
            return

        with conn.cursor() as cur:
            for old, new, _ in changes:
                cur.execute(
                    "UPDATE core.results SET division = %s WHERE division = %s",
                    (new, old),
                )
            cur.execute("ANALYZE core.results")
        conn.commit()

    print("\nDivision repair complete.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Seed core.dancer_aliases from transform/knowledge/dancer_aliases.py.

Usage:
    python scripts/seed_dancer_aliases.py --dry-run
    python scripts/seed_dancer_aliases.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from connection import connect  # noqa: E402
from transform.knowledge.dancer_aliases import DANCER_ALIAS_TO_ID  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    print(f"Aliases to seed: {len(DANCER_ALIAS_TO_ID)}")
    for alias, dancer_id in sorted(DANCER_ALIAS_TO_ID.items()):
        print(f"  {alias!r} -> {dancer_id}")

    if args.dry_run:
        print("\nDry run — no changes applied.")
        return

    with connect() as conn:
        with conn.cursor() as cur:
            for alias, dancer_id in DANCER_ALIAS_TO_ID.items():
                cur.execute(
                    """
                    INSERT INTO core.dancer_aliases (alias, dancer_id, source)
                    VALUES (%s, %s, 'knowledge/dancer_aliases.py')
                    ON CONFLICT (alias) DO UPDATE
                    SET dancer_id = EXCLUDED.dancer_id,
                        source = EXCLUDED.source
                    """,
                    (alias.strip(), dancer_id),
                )
        conn.commit()

    print("\nDancer aliases seeded.")


if __name__ == "__main__":
    main()

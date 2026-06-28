#!/usr/bin/env python3
"""Mark inactive catalog rows and alias phantom USA Grand Nationals ids.

Usage:
    python scripts/cleanup_event_catalog.py --dry-run
    python scripts/cleanup_event_catalog.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from build_event_catalog import rebuild_event_catalog  # noqa: E402
from catalog_registry import PHANTOM_ALIAS_TO_CANONICAL  # noqa: E402
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
                SELECT count(*) FROM core.event_catalog
                WHERE total_result_rows = 0
                  AND coalesce(registry_status, '') NOT IN ('inactive', 'merged')
                """
            )
            empty_count = int(cur.fetchone()[0])
            print(f"Empty catalog rows to mark inactive: {empty_count}")
            print(f"Phantom id aliases: {PHANTOM_ALIAS_TO_CANONICAL}")

            if args.dry_run:
                print("\nDry run — no changes applied.")
                return

            rebuild_event_catalog(conn)
        conn.commit()

    print("\nCatalog cleanup complete.")


if __name__ == "__main__":
    main()

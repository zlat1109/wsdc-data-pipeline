#!/usr/bin/env python3
"""Rebuild core.edition_division_tiers from core.results + tier rules.

Usage:
    python scripts/build_edition_tiers.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from build_edition_tiers import rebuild_edition_tiers  # noqa: E402
from connection import connect  # noqa: E402


def main() -> int:
    with connect() as conn:
        n, counts = rebuild_edition_tiers(conn)
        conn.commit()
    print(f"Rebuilt edition_division_tiers: {n:,} rows")
    for status, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {status}: {cnt:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

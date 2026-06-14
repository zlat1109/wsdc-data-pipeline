#!/usr/bin/env python3
"""Rebuild event catalog and editions in Supabase.

Usage:
    python scripts/build_event_catalog.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from build_event_catalog import rebuild_event_catalog
from connection import connect


def main() -> None:
    with connect() as conn:
        catalog_count, edition_count = rebuild_event_catalog(conn)
        conn.commit()
    print(f"event_catalog: {catalog_count} rows")
    print(f"event_editions: {edition_count} rows")


if __name__ == "__main__":
    main()

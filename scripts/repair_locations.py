#!/usr/bin/env python3
"""Apply location corrections and rebuild event catalog.

Usage:
    python scripts/repair_locations.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from db.normalize_core_locations import normalize_core_location_cities  # noqa: E402
from build_event_catalog import rebuild_event_catalog  # noqa: E402
from cleanup_event_catalog import apply_catalog_registry_cleanup  # noqa: E402
from connection import connect  # noqa: E402
from enrich_known_events import enrich_core_known_events  # noqa: E402


def main() -> None:
    with connect() as conn:
        updated = normalize_core_location_cities(conn)
        enrich_core_known_events(conn)
        catalog, editions = rebuild_event_catalog(conn)
        apply_catalog_registry_cleanup(conn)
        with conn.cursor() as cur:
            cur.execute("ANALYZE core.locations, core.event_editions, core.event_catalog")
        conn.commit()
    print(f"Location repair complete: cities_updated={updated}, catalog={catalog}, editions={editions}")


if __name__ == "__main__":
    main()

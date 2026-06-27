#!/usr/bin/env python3
"""Post-load data quality monitoring SQL checks.

Usage:
    python scripts/monitor_data_quality.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "db"))

from connection import connect  # noqa: E402

CHECKS = [
    (
        "results_null_location_id",
        "SELECT count(*) FROM core.results WHERE location_id IS NULL",
        0,
    ),
    (
        "split_names_same_geo",
        """
        WITH per AS (
            SELECT r.event_name_raw, r.event_id,
                   mode() WITHIN GROUP (ORDER BY l.event_city) AS city,
                   mode() WITHIN GROUP (ORDER BY l.event_country) AS country
            FROM core.results r
            LEFT JOIN core.locations l ON l.location_id = r.location_id
            WHERE r.event_name_raw IS NOT NULL
            GROUP BY 1, 2
        ),
        splits AS (
            SELECT event_name_raw FROM per GROUP BY 1 HAVING count(DISTINCT event_id) > 1
        )
        SELECT count(*) FROM (
            SELECT p.event_name_raw
            FROM per p JOIN splits s ON s.event_name_raw = p.event_name_raw
            GROUP BY p.event_name_raw
            HAVING count(DISTINCT p.city || '|' || coalesce(p.country, '')) = 1
        ) t
        """,
        0,
    ),
    (
        "noncanonical_divisions",
        """
        SELECT count(*) FROM core.results
        WHERE division IN ('All-Stars', 'Champions', 'Masters')
        """,
        0,
    ),
    (
        "points_history_drift",
        """
        SELECT count(*) FROM history.dancer_points_history h
        WHERE h.valid_to IS NULL AND NOT EXISTS (
            SELECT 1 FROM core.dancer_points p
            WHERE p.dancer_id = h.dancer_id AND p.role = h.role
              AND p.dance = h.dance AND p.level = h.level
              AND p.total_points = h.total_points
        )
        """,
        0,
    ),
]


def main() -> int:
    failures = 0
    with connect() as conn:
        with conn.cursor() as cur:
            for name, sql, expected in CHECKS:
                cur.execute(sql)
                value = int(cur.fetchone()[0])
                ok = value <= expected
                status = "OK" if ok else "FAIL"
                print(f"[{status}] {name}: {value} (expected <= {expected})")
                if not ok:
                    failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

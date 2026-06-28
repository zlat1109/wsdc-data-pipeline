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
from quality_checks import CORE_CHECKS  # noqa: E402

CHECKS = [(c.name, c.sql, c.max_value) for c in CORE_CHECKS]


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

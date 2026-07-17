#!/usr/bin/env python3
"""Audit event↔location mismatches (shared wrong location_id, calendar≠results).

Usage:
    python scripts/audit_event_location_mismatches.py
    python scripts/audit_event_location_mismatches.py --data-dir data
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from transform.geography.event_location_guard import (  # noqa: E402
    find_name_location_country_conflicts,
)
from transform.knowledge.events import EVENT_NAME_LOCATION_OVERRIDES  # noqa: E402


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    args = parser.parse_args()
    data_dir: Path = args.data_dir

    loc_rows = _load_csv(data_dir / "location_info.csv")
    loc = {r["location_id"]: r for r in loc_rows}
    results_rows = _load_csv(data_dir / "dancers_results_info.csv")

    event_loc: dict[str, Counter[str]] = defaultdict(Counter)
    for r in results_rows:
        en = (r.get("event_name") or "").strip()
        lid = (r.get("location_id") or "").strip()
        if en and lid:
            event_loc[en][lid] += 1

    sched: dict[str, dict[str, str]] = {}
    sched_path = data_dir / "scheduled_events.csv"
    if sched_path.exists():
        for r in _load_csv(sched_path):
            name = (r.get("canonical_name") or r.get("event_name") or "").strip()
            if name:
                sched[name] = r

    print("=== Covered by EVENT_NAME_LOCATION_OVERRIDES ===")
    for name, target in sorted(EVENT_NAME_LOCATION_OVERRIDES.items()):
        lids = event_loc.get(name)
        if not lids:
            print(f"  (no results) {name!r} → {target}")
            continue
        mode_lid, n = lids.most_common(1)[0]
        L = loc.get(mode_lid, {})
        print(
            f"  {n:5} {name!r} currently loc={mode_lid} "
            f"{L.get('event_city')}, {L.get('event_country')} → override {target}"
        )

    import pandas as pd

    results_df = pd.DataFrame(results_rows)
    location_df = pd.DataFrame(loc_rows)
    conflicts = find_name_location_country_conflicts(results_df, location_df)
    uncovered = [c for c in conflicts if c.event_name not in EVENT_NAME_LOCATION_OVERRIDES]

    print("\n=== A) Name-country hint disagrees with results location country ===")
    if not uncovered:
        print("  (none outside EVENT_NAME_LOCATION_OVERRIDES)")
    for c in uncovered:
        print(
            f"  {c.row_count:5} {c.event_name!r} loc={c.location_id} "
            f"{c.location_country} hints={list(c.name_hints)}"
        )

    print("\n=== B) Calendar/scheduled country ≠ results mode country ===")
    for en, lids in sorted(event_loc.items(), key=lambda kv: -sum(kv[1].values())):
        if en in EVENT_NAME_LOCATION_OVERRIDES:
            continue
        sch = sched.get(en)
        if not sch:
            continue
        expected = (sch.get("country") or "").strip()
        mode_lid, n = lids.most_common(1)[0]
        res_country = (loc.get(mode_lid, {}).get("event_country") or "").strip()
        if not expected or not res_country or expected == res_country:
            continue
        if expected.lower() in res_country.lower() or res_country.lower() in expected.lower():
            continue
        loc_raw = (sch.get("location_raw") or "").lower()
        if expected == "United States" and "canada" in loc_raw and res_country == "Canada":
            continue
        # South Korea / Republic of Korea alias residual
        if {"south korea", "republic of korea"} == {expected.lower(), res_country.lower()}:
            continue
        print(
            f"  {n:5} {en!r}\n"
            f"        results loc {mode_lid} → {res_country}; "
            f"scheduled {expected} ({sch.get('location_raw')})"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

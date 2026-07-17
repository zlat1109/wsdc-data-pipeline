#!/usr/bin/env python3
"""Audit event↔location mismatches (shared wrong location_id, calendar≠results).

Usage:
    python scripts/audit_event_location_mismatches.py
    python scripts/audit_event_location_mismatches.py --data-dir data
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from transform.knowledge.events import EVENT_NAME_LOCATION_OVERRIDES  # noqa: E402

COUNTRY_HINTS = [
    (r"\bsweden\b|\bswedish\b|\bstockholm\b", "Sweden"),
    (r"\bfrance\b|\bfrench\b|\bparis\b|\btoulouse\b|\bannecy\b", "France"),
    (r"\bcanada\b|\btoronto\b|\bvancouver\b|\bmontreal\b", "Canada"),
    (r"\bireland\b|\bdublin\b|\bdundalk\b", "Ireland"),
    (r"\bbulgaria\b|\bsofia\b", "Bulgaria"),
    (r"\bhawaii\b|\baloha\b|\bwailea\b|\bmaui\b", "United States"),
]


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _hint_countries(name: str) -> list[str]:
    n = name.lower()
    return [country for pat, country in COUNTRY_HINTS if re.search(pat, n)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    args = parser.parse_args()
    data_dir: Path = args.data_dir

    loc = {r["location_id"]: r for r in _load_csv(data_dir / "location_info.csv")}
    event_loc: dict[str, Counter[str]] = defaultdict(Counter)
    loc_events: dict[str, Counter[str]] = defaultdict(Counter)
    for r in _load_csv(data_dir / "dancers_results_info.csv"):
        en = (r.get("event_name") or "").strip()
        lid = (r.get("location_id") or "").strip()
        if en and lid:
            event_loc[en][lid] += 1
            loc_events[lid][en] += 1

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

    print("\n=== A) Name-country hint disagrees with results location country ===")
    for lid, events in sorted(loc_events.items(), key=lambda kv: -sum(kv[1].values())):
        L = loc.get(lid, {})
        country = (L.get("event_country") or "").strip()
        mismatched = []
        for en, n in events.items():
            if en in EVENT_NAME_LOCATION_OVERRIDES:
                continue
            hints = _hint_countries(en)
            if hints and country and all(h != country for h in hints):
                mismatched.append((en, n, hints))
        if not mismatched:
            continue
        print(f"\nloc {lid} {L.get('event_city')}, {country}")
        for en, n, hints in sorted(mismatched, key=lambda x: -x[1]):
            print(f"  {n:5} {en!r} name_hints={hints}")

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
        # Known false positive: Waterloo Ontario scheduled flag sometimes says USA
        # while location_raw is Canada and results are correct.
        loc_raw = (sch.get("location_raw") or "").lower()
        if expected == "United States" and "canada" in loc_raw and res_country == "Canada":
            continue
        print(
            f"  {n:5} {en!r}\n"
            f"        results loc {mode_lid} → {res_country}; "
            f"scheduled {expected} ({sch.get('location_raw')})"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

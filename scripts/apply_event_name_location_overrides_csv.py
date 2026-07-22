#!/usr/bin/env python3
"""Apply EVENT_NAME_LOCATION_OVERRIDES to local export CSVs.

Remaps dancers_results_info.location_id (+ optional event_editions /
events_wsdc / event_catalog fields) so Champion News and Tableau exports
match the durable override map without waiting for a full re-parse.

Usage:
    python scripts/apply_event_name_location_overrides_csv.py --dry-run
    python scripts/apply_event_name_location_overrides_csv.py --apply
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from transform.geography.resolve import (  # noqa: E402
    build_location_lookup,
    location_lookup_key_from_text,
    _canonical_location_raw,
    _norm,
)
from transform.knowledge.apply import (  # noqa: E402
    force_result_locations_from_event_name_overrides,
)
from transform.knowledge.events import (  # noqa: E402
    EVENT_NAME_LOCATION_OVERRIDES,
    KNOWN_EVENT_METADATA,
)


def _resolve_target_ids(location_df: pd.DataFrame) -> dict[str, str]:
    lookup = build_location_lookup(location_df)
    out: dict[str, str] = {}
    for name, target in EVENT_NAME_LOCATION_OVERRIDES.items():
        raw = _canonical_location_raw(_norm(target))
        key = location_lookup_key_from_text(raw)
        loc_id = lookup.get(key) or lookup.get(raw.lower())
        if loc_id:
            out[name] = str(loc_id)
        else:
            print(f"⚠️  cannot resolve {name!r} → {target!r}")
    return out


def _update_editions(path: Path, name_to_lid: dict[str, str], dry_run: bool) -> int:
    if not path.exists():
        return 0
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))
    if not rows:
        return 0
    fields = list(rows[0].keys())
    changed = 0
    loc = {
        r["location_id"]: r
        for r in csv.DictReader((path.parent / "location_info.csv").open(encoding="utf-8-sig"))
    }
    for row in rows:
        name = (row.get("event_name") or "").strip()
        if name not in name_to_lid:
            continue
        new_lid = name_to_lid[name]
        if row.get("location_id") == new_lid:
            continue
        changed += 1
        if dry_run:
            continue
        L = loc.get(new_lid, {})
        row["location_id"] = new_lid
        if "place_city" in row:
            row["place_city"] = L.get("event_city") or row.get("place_city") or ""
        if "place_state" in row:
            row["place_state"] = L.get("event_state") or ""
        if "place_country" in row:
            row["place_country"] = L.get("event_country") or row.get("place_country") or ""
        if "location_raw" in row:
            row["location_raw"] = (
                L.get("event_location")
                or L.get("event_location_standardized")
                or row.get("location_raw")
                or ""
            )
        if "typical_location" in row:
            row["typical_location"] = (
                L.get("event_location_standardized")
                or L.get("event_location")
                or row.get("typical_location")
                or ""
            )
    if not dry_run and changed:
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    return changed


def _update_events_wsdc(path: Path, name_to_target: dict[str, str], dry_run: bool) -> int:
    if not path.exists():
        return 0
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))
    if not rows:
        return 0
    fields = list(rows[0].keys())
    changed = 0
    for row in rows:
        name = (row.get("name") or "").strip()
        if name not in name_to_target:
            continue
        target = name_to_target[name]
        if (row.get("location") or "").strip() == target:
            continue
        changed += 1
        if not dry_run:
            row["location"] = target
    if not dry_run and changed:
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    return changed


def _update_catalog(path: Path, dry_run: bool) -> int:
    if not path.exists():
        return 0
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))
    if not rows:
        return 0
    fields = list(rows[0].keys())
    meta_by_id = {str(eid): meta for eid, meta in KNOWN_EVENT_METADATA.items()}
    changed = 0
    for row in rows:
        eid = str(row.get("event_id") or "")
        meta = meta_by_id.get(eid)
        if not meta:
            continue
        loc = meta.get("location") or {}
        typical = meta.get("typical_location") or loc.get("event_location") or ""
        if not typical:
            continue
        before = (
            row.get("typical_location"),
            row.get("typical_city"),
            row.get("typical_country"),
        )
        after = (
            typical,
            loc.get("event_city") or row.get("typical_city"),
            loc.get("event_country") or row.get("typical_country"),
        )
        if before == after:
            continue
        changed += 1
        if dry_run:
            continue
        row["typical_location"] = after[0]
        if "typical_city" in row:
            row["typical_city"] = after[1] or ""
        if "typical_state" in row:
            row["typical_state"] = loc.get("event_state") or ""
        if "typical_country" in row:
            row["typical_country"] = after[2] or ""
    if not dry_run and changed:
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.dry_run == args.apply:
        print("Specify exactly one of --dry-run or --apply")
        return 2
    dry_run = args.dry_run
    data_dir: Path = args.data_dir

    location_df = pd.read_csv(data_dir / "location_info.csv", dtype=str)
    results_df = pd.read_csv(data_dir / "dancers_results_info.csv", dtype=str)
    name_to_lid = _resolve_target_ids(location_df)
    name_to_target = dict(EVENT_NAME_LOCATION_OVERRIDES)

    before = Counter(
        (r.event_name, str(r.location_id))
        for r in results_df.itertuples(index=False)
        if r.event_name in name_to_lid
    )
    out, forced = force_result_locations_from_event_name_overrides(results_df, location_df)
    print(f"results rows that would change: {forced}")
    for name, lid in sorted(name_to_lid.items()):
        n = int((results_df["event_name"] == name).sum())
        cur = (
            results_df.loc[results_df["event_name"] == name, "location_id"]
            .mode(dropna=True)
            .tolist()
        )
        print(f"  {name}: {n} rows, mode lid={cur[:1]} → {lid}")

    editions_n = _update_editions(data_dir / "event_editions.csv", name_to_lid, dry_run=True)
    wsdc_n = _update_events_wsdc(data_dir / "events_wsdc.csv", name_to_target, dry_run=True)
    catalog_n = _update_catalog(data_dir / "event_catalog.csv", dry_run=True)
    print(f"event_editions rows to update: {editions_n}")
    print(f"events_wsdc rows to update: {wsdc_n}")
    print(f"event_catalog rows to update: {catalog_n}")

    if dry_run:
        print("dry-run only; no files written")
        return 0

    out.to_csv(data_dir / "dancers_results_info.csv", index=False)
    _update_editions(data_dir / "event_editions.csv", name_to_lid, dry_run=False)
    _update_events_wsdc(data_dir / "events_wsdc.csv", name_to_target, dry_run=False)
    _update_catalog(data_dir / "event_catalog.csv", dry_run=False)
    print(f"✅ applied: results forced={forced} (before sample size {len(before)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

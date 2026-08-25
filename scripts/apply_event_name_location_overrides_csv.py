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
    force_events_wsdc_locations_from_event_name_overrides,
    force_result_locations_from_event_name_overrides,
)
from transform.knowledge.event_aliases import apply_event_name_year_splits  # noqa: E402
from transform.knowledge.merge_map import apply_merge_event_id_map  # noqa: E402
from transform.knowledge.events import (  # noqa: E402
    EVENT_NAME_LOCATION_OVERRIDES,
    EVENT_NAME_YEAR_LOCATION_OVERRIDES,
    KNOWN_EVENT_METADATA,
)


def _resolve_text_to_lid(lookup: dict[str, str], target: str) -> str | None:
    raw = _canonical_location_raw(_norm(target))
    key = location_lookup_key_from_text(raw)
    loc_id = lookup.get(key) or lookup.get(raw.lower())
    return str(loc_id) if loc_id else None


def _resolve_target_ids(location_df: pd.DataFrame) -> dict[str, str]:
    lookup = build_location_lookup(location_df)
    out: dict[str, str] = {}
    for name, target in EVENT_NAME_LOCATION_OVERRIDES.items():
        loc_id = _resolve_text_to_lid(lookup, target)
        if loc_id:
            out[name] = loc_id
        else:
            print(f"⚠️  cannot resolve {name!r} → {target!r}")
    return out


def _target_for_name_year(name: str, year: int | None) -> str | None:
    """Flat override, then year-scoped override (same order as force_*)."""
    target = EVENT_NAME_LOCATION_OVERRIDES.get(name)
    if year is None:
        return target
    for (n, y0, y1), loc in EVENT_NAME_YEAR_LOCATION_OVERRIDES.items():
        if n == name and y0 <= year <= y1:
            return loc
    return target


def _parse_year(row: dict[str, str], *keys: str) -> int | None:
    for key in keys:
        raw = (row.get(key) or "").strip()
        if not raw:
            continue
        try:
            return int(float(raw))
        except ValueError:
            continue
    return None


def _apply_edition_location(row: dict[str, str], loc_row: dict[str, str]) -> None:
    row["location_id"] = loc_row.get("location_id") or row.get("location_id") or ""
    if "place_city" in row:
        row["place_city"] = loc_row.get("event_city") or row.get("place_city") or ""
    if "place_state" in row:
        row["place_state"] = loc_row.get("event_state") or ""
    if "place_country" in row:
        row["place_country"] = loc_row.get("event_country") or row.get("place_country") or ""
    if "location_raw" in row:
        row["location_raw"] = (
            loc_row.get("event_location")
            or loc_row.get("event_location_standardized")
            or row.get("location_raw")
            or ""
        )
    if "typical_location" in row:
        row["typical_location"] = (
            loc_row.get("event_location_standardized")
            or loc_row.get("event_location")
            or row.get("typical_location")
            or ""
        )


def _update_editions(path: Path, location_df: pd.DataFrame, dry_run: bool) -> int:
    if not path.exists():
        return 0
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))
    if not rows:
        return 0
    fields = list(rows[0].keys())
    lookup = build_location_lookup(location_df)
    loc = {
        str(r["location_id"]): r
        for r in location_df.to_dict(orient="records")
        if str(r.get("location_id") or "")
    }
    override_names = set(EVENT_NAME_LOCATION_OVERRIDES) | {
        name for name, _y0, _y1 in EVENT_NAME_YEAR_LOCATION_OVERRIDES
    }
    changed = 0
    for row in rows:
        name = (row.get("event_name") or "").strip()
        if name not in override_names:
            continue
        year = _parse_year(row, "event_year", "year")
        target = _target_for_name_year(name, year)
        if not target:
            continue
        new_lid = _resolve_text_to_lid(lookup, target)
        if not new_lid:
            continue
        L = loc.get(new_lid, {})
        want_raw = L.get("event_location") or target
        if row.get("location_id") == new_lid and (row.get("location_raw") or "") == want_raw:
            continue
        changed += 1
        if dry_run:
            continue
        _apply_edition_location(row, {**L, "location_id": new_lid})
    if not dry_run and changed:
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    return changed


def _update_events_wsdc(path: Path, dry_run: bool) -> int:
    if not path.exists():
        return 0
    df = pd.read_csv(path, dtype=str)
    out, changed = force_events_wsdc_locations_from_event_name_overrides(df)
    if dry_run:
        return changed
    if changed:
        out.to_csv(path, index=False)
    return changed


def _detect_newline(path: Path) -> str:
    raw = path.read_bytes()
    return "\r\n" if b"\r\n" in raw else "\n"


def _update_catalog(path: Path, dry_run: bool) -> int:
    if not path.exists():
        return 0
    newline = _detect_newline(path)
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
            w = csv.DictWriter(f, fieldnames=fields, lineterminator=newline)
            w.writeheader()
            w.writerows(rows)
    return changed


_YEAR_SPLIT_FILES: tuple[tuple[str, str], ...] = (
    ("dancers_results_info.csv", "event_name"),
    ("events_wsdc.csv", "name"),
    ("event_editions.csv", "event_name"),
    ("edition_division_tiers.csv", "event_name"),
    ("edition_division_entries.csv", "event_name"),
)
_MERGE_ID_FILES: tuple[tuple[str, str], ...] = (
    ("events_wsdc.csv", "id"),
    ("event_editions.csv", "event_id"),
    ("edition_division_tiers.csv", "event_id"),
    ("edition_division_entries.csv", "event_id"),
)


_ID_COLS = ("event_name_id", "id", "event_id")


def _count_year_split_changes(before: pd.DataFrame, after: pd.DataFrame, name_col: str) -> int:
    changed = after[name_col].astype(str) != before[name_col].astype(str)
    for col in _ID_COLS:
        if col in before.columns and col in after.columns:
            changed = changed | (after[col].astype(str) != before[col].astype(str))
    return int(changed.sum())


def _apply_year_splits(path: Path, name_col: str, dry_run: bool) -> int:
    """Re-apply EVENT_NAME_YEAR_SPLITS so export views (one name per event_id) do not collapse rebrands."""
    if not path.exists():
        return 0
    df = pd.read_csv(path, dtype=str)
    if name_col not in df.columns or "event_year" not in df.columns:
        return 0
    out = apply_event_name_year_splits(df)
    changed = _count_year_split_changes(df, out, name_col)
    if dry_run or not changed:
        return changed
    out.to_csv(path, index=False)
    return changed


def _apply_merge_ids(path: Path, id_col: str, dry_run: bool) -> int:
    """Collapse catalog ghosts (MERGE_EVENT_ID_MAP) on export id columns."""
    if not path.exists():
        return 0
    df = pd.read_csv(path, dtype=str)
    if id_col not in df.columns:
        return 0
    out = apply_merge_event_id_map(df, column=id_col, table=path.name)
    changed = int((out[id_col].astype(str) != df[id_col].astype(str)).sum())
    if dry_run or not changed:
        return changed
    out.to_csv(path, index=False)
    return changed


def apply_overrides(data_dir: Path, *, dry_run: bool = False) -> int:
    """Remap export CSVs from name/year location overrides. Returns forced result rows."""
    split_counts: dict[str, int] = {}
    for filename, name_col in _YEAR_SPLIT_FILES:
        split_counts[filename] = _apply_year_splits(
            data_dir / filename, name_col, dry_run=True
        )
    print("year-split rows to update:")
    for filename, n in split_counts.items():
        print(f"  {filename}: {n}")
    if not dry_run:
        for filename, name_col in _YEAR_SPLIT_FILES:
            _apply_year_splits(data_dir / filename, name_col, dry_run=False)

    merge_counts: dict[str, int] = {}
    for filename, id_col in _MERGE_ID_FILES:
        merge_counts[filename] = _apply_merge_ids(
            data_dir / filename, id_col, dry_run=True
        )
    print("merge-id rows to update:")
    for filename, n in merge_counts.items():
        print(f"  {filename}: {n}")
    if not dry_run:
        for filename, id_col in _MERGE_ID_FILES:
            _apply_merge_ids(data_dir / filename, id_col, dry_run=False)

    location_df = pd.read_csv(data_dir / "location_info.csv", dtype=str)
    results_df = pd.read_csv(data_dir / "dancers_results_info.csv", dtype=str)
    name_to_lid = _resolve_target_ids(location_df)

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
        print(f"  {name}: {n} rows, mode lid={cur[:1]} → flat {lid}")

    editions_n = _update_editions(data_dir / "event_editions.csv", location_df, dry_run=True)
    wsdc_n = _update_events_wsdc(data_dir / "events_wsdc.csv", dry_run=True)
    catalog_n = _update_catalog(data_dir / "event_catalog.csv", dry_run=True)
    print(f"event_editions rows to update: {editions_n}")
    print(f"events_wsdc rows to update: {wsdc_n}")
    print(f"event_catalog rows to update: {catalog_n}")

    if dry_run:
        print("dry-run only; no files written")
        return forced

    out.to_csv(data_dir / "dancers_results_info.csv", index=False)
    _update_editions(data_dir / "event_editions.csv", location_df, dry_run=False)
    _update_events_wsdc(data_dir / "events_wsdc.csv", dry_run=False)
    _update_catalog(data_dir / "event_catalog.csv", dry_run=False)
    print(f"✅ applied: results forced={forced} (before sample size {len(before)})")
    return forced


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.dry_run == args.apply:
        print("Specify exactly one of --dry-run or --apply")
        return 2
    apply_overrides(args.data_dir, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

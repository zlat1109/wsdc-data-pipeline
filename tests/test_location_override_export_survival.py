"""Export CSVs must keep EVENT_NAME_LOCATION_OVERRIDES after full-parse refresh."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import pandas as pd
import pytest

from transform.geography.resolve import (
    _canonical_location_raw,
    build_location_lookup,
    location_lookup_key_from_text,
)
from transform.geography.utils import norm_value
from transform.knowledge.events import EVENT_NAME_LOCATION_OVERRIDES

DATA = Path(__file__).resolve().parents[1] / "data"


def _resolve_override_lids(location_df: pd.DataFrame) -> dict[str, str]:
    lookup = build_location_lookup(location_df)
    out: dict[str, str] = {}
    for name, target in EVENT_NAME_LOCATION_OVERRIDES.items():
        raw = _canonical_location_raw(norm_value(target))
        key = location_lookup_key_from_text(raw)
        lid = lookup.get(key) or lookup.get(raw.lower())
        if lid:
            out[name] = str(lid)
    return out


@pytest.mark.skipif(not (DATA / "location_info.csv").exists(), reason="no export data")
def test_results_mode_location_matches_overrides():
    location_df = pd.read_csv(DATA / "location_info.csv", dtype=str)
    name_to_lid = _resolve_override_lids(location_df)
    assert name_to_lid, "expected resolvable EVENT_NAME_LOCATION_OVERRIDES"

    modes: dict[str, Counter[str]] = {}
    with (DATA / "dancers_results_info.csv").open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("event_name") or "").strip()
            if name not in name_to_lid:
                continue
            modes.setdefault(name, Counter())[str(row.get("location_id") or "")] += 1

    failures: list[str] = []
    for name, want in sorted(name_to_lid.items()):
        counts = modes.get(name)
        if not counts:
            continue
        mode = counts.most_common(1)[0][0]
        if mode != want:
            failures.append(f"{name}: mode location_id={mode} want={want} ({dict(counts)})")
    assert not failures, "results export drifted from overrides:\n" + "\n".join(failures)


@pytest.mark.skipif(not (DATA / "event_editions.csv").exists(), reason="no export data")
def test_editions_location_matches_overrides():
    location_df = pd.read_csv(DATA / "location_info.csv", dtype=str)
    name_to_lid = _resolve_override_lids(location_df)
    loc_by_id = {
        str(r.location_id): r
        for r in location_df.itertuples(index=False)
        if str(getattr(r, "location_id", "") or "")
    }

    failures: list[str] = []
    with (DATA / "event_editions.csv").open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("event_name") or "").strip()
            want = name_to_lid.get(name)
            if not want:
                continue
            got = str(row.get("location_id") or "")
            if got == want:
                continue
            L = loc_by_id.get(want)
            failures.append(
                f"{name} {row.get('event_year')}-{row.get('event_month')}: "
                f"location_id={got} want={want}"
                + (f" ({getattr(L, 'event_city', '')})" if L is not None else "")
            )
    assert not failures, "event_editions drifted from overrides:\n" + "\n".join(failures)


@pytest.mark.skipif(not (DATA / "events_wsdc.csv").exists(), reason="no export data")
def test_events_wsdc_location_matches_overrides():
    failures: list[str] = []
    with (DATA / "events_wsdc.csv").open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("name") or "").strip()
            want = EVENT_NAME_LOCATION_OVERRIDES.get(name)
            if not want:
                continue
            got = (row.get("location") or "").strip()
            raw = _canonical_location_raw(norm_value(want))
            if got != raw:
                failures.append(
                    f"{name} {row.get('event_year')}: location={got!r} want={raw!r}"
                )
    assert not failures, "events_wsdc drifted from overrides:\n" + "\n".join(failures)

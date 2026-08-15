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
from transform.knowledge.events import (
    EVENT_NAME_LOCATION_OVERRIDES,
    EVENT_NAME_YEAR_LOCATION_OVERRIDES,
)

DATA = Path(__file__).resolve().parents[1] / "data"


def _resolve_lid(location_df: pd.DataFrame, target: str) -> str | None:
    lookup = build_location_lookup(location_df)
    raw = _canonical_location_raw(norm_value(target))
    key = location_lookup_key_from_text(raw)
    lid = lookup.get(key) or lookup.get(raw.lower())
    return str(lid) if lid else None


def _resolve_override_lids(location_df: pd.DataFrame) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, target in EVENT_NAME_LOCATION_OVERRIDES.items():
        lid = _resolve_lid(location_df, target)
        if lid:
            out[name] = lid
    return out


def _year_override_want(
    name: str, year: int | None, location_df: pd.DataFrame
) -> str | None:
    if year is None:
        return None
    for (ov_name, y0, y1), target in EVENT_NAME_YEAR_LOCATION_OVERRIDES.items():
        if ov_name != name or year < y0 or year > y1:
            continue
        return _resolve_lid(location_df, target)
    return None


@pytest.mark.skipif(not (DATA / "location_info.csv").exists(), reason="no export data")
def test_results_mode_location_matches_overrides():
    location_df = pd.read_csv(DATA / "location_info.csv", dtype=str)
    name_to_lid = _resolve_override_lids(location_df)
    assert name_to_lid, "expected resolvable EVENT_NAME_LOCATION_OVERRIDES"

    override_names = set(name_to_lid) | {
        name for name, _y0, _y1 in EVENT_NAME_YEAR_LOCATION_OVERRIDES
    }
    failures: list[str] = []
    with (DATA / "dancers_results_info.csv").open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("event_name") or "").strip()
            if name not in override_names:
                continue
            year_raw = row.get("event_year")
            try:
                year = int(year_raw) if year_raw not in (None, "") else None
            except ValueError:
                year = None
            want = _year_override_want(name, year, location_df) or name_to_lid.get(name)
            if not want:
                continue
            got = str(row.get("location_id") or "")
            if got != want:
                failures.append(
                    f"{name} year={year_raw}: location_id={got} want={want}"
                )
    assert not failures, "results export drifted from overrides:\n" + "\n".join(
        failures[:40]
    ) + (f"\n... and {len(failures) - 40} more" if len(failures) > 40 else "")


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
            year_raw = row.get("event_year")
            try:
                year = int(year_raw) if year_raw not in (None, "") else None
            except ValueError:
                year = None
            want = _year_override_want(name, year, location_df) or name_to_lid.get(name)
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
            year_raw = row.get("event_year")
            try:
                year = int(year_raw) if year_raw not in (None, "") else None
            except ValueError:
                year = None
            year_target = None
            for (ov_name, y0, y1), target in EVENT_NAME_YEAR_LOCATION_OVERRIDES.items():
                if ov_name == name and year is not None and y0 <= year <= y1:
                    year_target = target
                    break
            want = year_target or EVENT_NAME_LOCATION_OVERRIDES.get(name)
            if not want:
                continue
            got = (row.get("location") or "").strip()
            raw = _canonical_location_raw(norm_value(want))
            if got != raw:
                failures.append(
                    f"{name} {row.get('event_year')}: location={got!r} want={raw!r}"
                )
    assert not failures, "events_wsdc drifted from overrides:\n" + "\n".join(failures)


@pytest.mark.skipif(not (DATA / "location_info.csv").exists(), reason="no export data")
def test_year_overrides_resolve_in_location_info():
    """Every year-scoped target must exist in location_info (else force skips)."""
    location_df = pd.read_csv(DATA / "location_info.csv", dtype=str)
    missing = []
    for (name, y0, y1), target in EVENT_NAME_YEAR_LOCATION_OVERRIDES.items():
        if not _resolve_lid(location_df, target):
            missing.append(f"{name} [{y0}-{y1}] → {target}")
    assert not missing, "unresolvable year location overrides:\n" + "\n".join(missing)

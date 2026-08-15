"""Greater Boston suburb locations must resolve from override labels."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from transform.geography.resolve import (
    build_location_lookup,
    location_lookup_key_from_text,
    _canonical_location_raw,
    _norm,
)
from transform.knowledge.events import (
    EVENT_NAME_LOCATION_OVERRIDES,
    EVENT_NAME_YEAR_LOCATION_OVERRIDES,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _resolve(lookup: dict[str, str], target: str) -> str | None:
    raw = _canonical_location_raw(_norm(target))
    key = location_lookup_key_from_text(raw)
    lid = lookup.get(key) or lookup.get(raw.lower())
    return str(lid) if lid else None


def test_boston_suburb_location_registry_rows_exist():
    loc = pd.read_csv(DATA_DIR / "location_info.csv", dtype=str)
    by_id = {str(r.location_id): r for r in loc.itertuples(index=False)}
    assert by_id["396"].event_city == "Mansfield"
    assert by_id["396"].event_location == "Mansfield (Boston), MA, United States"
    assert by_id["397"].event_city == "Woburn"
    assert by_id["397"].event_location == "Woburn (Boston), MA, United States"
    assert by_id["70"].event_location == "Newton (Boston), MA, United States"
    assert by_id["79"].event_location == "Burlington (Boston), MA, United States"
    assert by_id["71"].event_location == "Framingham (Boston), MA, United States"


def test_boston_suburb_overrides_resolve_to_expected_ids():
    loc = pd.read_csv(DATA_DIR / "location_info.csv", dtype=str)
    lookup = build_location_lookup(loc)
    assert _resolve(lookup, EVENT_NAME_LOCATION_OVERRIDES["Summer Hummer"]) == "397"
    assert (
        _resolve(lookup, EVENT_NAME_LOCATION_OVERRIDES["New England Dance Festival"])
        == "70"
    )
    assert (
        _resolve(lookup, EVENT_NAME_LOCATION_OVERRIDES["New Year's Dancin' Eve"]) == "79"
    )
    assert _resolve(lookup, EVENT_NAME_LOCATION_OVERRIDES["Countdown Swing Boston"]) == "8"
    assert (
        _resolve(
            lookup,
            EVENT_NAME_YEAR_LOCATION_OVERRIDES[("Countdown Swing Boston", 2025, 2099)],
        )
        == "396"
    )
    # Legacy labels still alias to suburb rows.
    assert _resolve(lookup, "Newton, MA, United States") == "70"
    assert _resolve(lookup, "Burlington, MA, United States") == "79"

"""Tests for trial/list ensure_location and schedule→results seeding."""

from __future__ import annotations

import pandas as pd

from transform.geography.ensure_location import (
    SOURCE_CITY_CANONICAL,
    SOURCE_GOOGLE_MAPS,
    SOURCE_LOCATION_INFO,
    SOURCE_UNRESOLVED,
    ensure_location,
)
from transform.geography.schedule_locations import (
    assign_schedule_locations,
    seed_result_locations_from_schedule,
)


def _loc_df(*rows: dict) -> pd.DataFrame:
    cols = [
        "location_id",
        "event_city",
        "event_state",
        "event_country",
        "latitude",
        "longitude",
        "event_location",
        "event_location_standardized",
        "coordinates_valid",
    ]
    return pd.DataFrame(list(rows)).reindex(columns=cols, fill_value="")


def test_ensure_location_reuses_existing_with_coords():
    locations = _loc_df(
        {
            "location_id": "129",
            "event_city": "Munich",
            "event_country": "Germany",
            "latitude": "48.13",
            "longitude": "11.58",
            "event_location": "Munich, Germany",
            "event_location_standardized": "Munich, Germany",
            "coordinates_valid": "t",
        }
    )
    result, out = ensure_location(
        "Munich, Bavaria, Germany",
        location_df=locations,
        allow_geocode=False,
    )
    assert result.location_id == "129"
    assert result.source == SOURCE_LOCATION_INFO
    assert not result.created
    assert len(out) == 1


def test_ensure_location_creates_with_geocode_fn():
    locations = _loc_df()

    def fake_geocode(query: str):
        assert "Nowhereville" in query
        return (1.0, 2.0)

    result, out = ensure_location(
        "Nowhereville, Testland",
        location_df=locations,
        geocode_fn=fake_geocode,
        allow_geocode=True,
    )
    assert result.created
    assert result.location_id is not None
    assert result.source == SOURCE_GOOGLE_MAPS
    assert float(out.iloc[0]["latitude"]) == 1.0
    assert float(out.iloc[0]["longitude"]) == 2.0


def test_ensure_location_canonical_coords_without_geocode():
    locations = _loc_df()
    result, out = ensure_location(
        "Stockholm, Sweden",
        location_df=locations,
        allow_geocode=False,
    )
    assert result.created
    assert result.source == SOURCE_CITY_CANONICAL
    assert float(out.iloc[0]["latitude"]) == 59.3251172


def test_ensure_location_unresolved_when_geocode_fails():
    locations = _loc_df()
    result, out = ensure_location(
        "Mysterytown, Nowhere",
        location_df=locations,
        geocode_fn=lambda q: None,
        allow_geocode=True,
    )
    assert result.created
    assert result.source == SOURCE_UNRESOLVED
    assert result.review_reason == "created_without_coords"
    assert str(out.iloc[0]["latitude"]).strip() in {"", "nan"}


def test_assign_schedule_locations_only_trials():
    locations = _loc_df(
        {
            "location_id": "129",
            "event_city": "Munich",
            "event_country": "Germany",
            "latitude": "48.13",
            "longitude": "11.58",
            "event_location": "Munich, Germany",
            "event_location_standardized": "Munich, Germany",
            "coordinates_valid": "t",
        }
    )
    events = [
        {
            "event_name": "Infinite Swing",
            "status_event": "Trial Event",
            "location_raw": "Munich, Bavaria, Germany",
            "country": "Germany",
        },
        {
            "event_name": "Dutch Open West Coast Swing",
            "status_event": "Registry Event",
            "location_raw": "Venray, Netherlands",
            "country": "Netherlands",
        },
    ]
    out, locations, review = assign_schedule_locations(
        events, locations, allow_geocode=False
    )
    assert out[0]["location_id"] in {129, "129"}
    assert out[1].get("location_id") in (None, "", 0) or "location_id" not in out[1] or not out[1].get("location_id")
    # Registry must not get a new assignment from this path
    assert out[1].get("location_id") in (None, "")
    assert review == []


def test_seed_results_fills_empty_and_forces_trial():
    scheduled = pd.DataFrame(
        [
            {
                "event_name": "Brand New Trial Fest",
                "status_event": "Trial Event",
                "location_id": "129",
            },
            {
                "event_name": "Some Registry",
                "status_event": "Registry Event",
                "location_id": "8",
            },
        ]
    )
    results = pd.DataFrame(
        [
            {"event_name": "Brand New Trial Fest", "location_id": "227"},  # wrong
            {"event_name": "Some Registry", "location_id": "99"},  # keep existing
            {"event_name": "Some Registry", "location_id": ""},  # fill empty
        ]
    )
    out, n = seed_result_locations_from_schedule(results, scheduled)
    assert n == 2
    assert str(out.loc[0, "location_id"]) == "129"
    assert str(out.loc[1, "location_id"]) == "99"
    assert str(out.loc[2, "location_id"]) == "8"


def test_seed_respects_event_name_overrides():
    from transform.knowledge.events import EVENT_NAME_LOCATION_OVERRIDES

    # Pick any known override name if present; otherwise skip-shaped assert
    name = next(iter(EVENT_NAME_LOCATION_OVERRIDES), None)
    if not name:
        return
    scheduled = pd.DataFrame(
        [{"event_name": name, "status_event": "Trial Event", "location_id": "999"}]
    )
    results = pd.DataFrame([{"event_name": name, "location_id": "1"}])
    out, n = seed_result_locations_from_schedule(results, scheduled)
    assert n == 0
    assert str(out.loc[0, "location_id"]) == "1"

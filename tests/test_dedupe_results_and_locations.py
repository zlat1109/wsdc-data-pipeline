"""Tests for result-row and location_info deduplication."""

import pandas as pd

from transform.data_preprocessing import dedupe_result_rows
from transform.geography.resolve import (
    build_location_lookup,
    dedupe_location_info,
    location_lookup_key_from_text,
    resolve_result_location_ids,
)


def test_dedupe_result_rows_drops_exact_duplicates():
    df = pd.DataFrame(
        [
            {
                "dancer_id": "1000",
                "event_dance": "West Coast Swing",
                "event_competition": "Advanced",
                "event_role": "follower",
                "event_name": "New England Swing Dance Championships",
                "event_result": "2",
                "event_points": "0",
                "event_year": "2001",
                "event_month": "9",
                "location_id": "78",
            },
            {
                "dancer_id": "1000",
                "event_dance": "West Coast Swing",
                "event_competition": "Advanced",
                "event_role": "follower",
                "event_name": "New England Swing Dance Championships",
                "event_result": "2",
                "event_points": "0",
                "event_year": "2001",
                "event_month": "9",
                "location_id": "78",
            },
        ]
    )
    out, dropped = dedupe_result_rows(df)
    assert dropped == 1
    assert len(out) == 1


def test_location_lookup_key_collapses_phoenix_variants():
    a = location_lookup_key_from_text("Phoenix, AZ, United States")
    b = location_lookup_key_from_text("Phoenix, AZ, USA")
    assert a == b == "phoenix, az, united states"


def test_location_lookup_key_collapses_london_variants():
    a = location_lookup_key_from_text("London, England, United Kingdom")
    b = location_lookup_key_from_text("London, United Kingdom")
    assert a == b == "london, united kingdom"


def test_resolve_reuses_existing_phoenix_id_for_variant_text():
    location_info = pd.DataFrame(
        [
            {
                "location_id": "3",
                "event_city": "Phoenix",
                "event_state": "Arizona",
                "event_country": "United States",
                "latitude": "",
                "longitude": "",
                "event_location": "Phoenix, AZ, United States",
                "event_location_standardized": "Phoenix, AZ",
                "coordinates_valid": "",
            }
        ]
    )
    results = pd.DataFrame(
        [
            {
                "dancer_id": "1",
                "event_location": "Phoenix, AZ, USA",
                "location_id": "",
            }
        ]
    )
    resolved, locations = resolve_result_location_ids(results, location_info)
    assert resolved.loc[0, "location_id"] == "3"
    assert len(locations) == 1


def test_build_location_lookup_registers_canonical_key():
    location_info = pd.DataFrame(
        [
            {
                "location_id": "107",
                "event_city": "London",
                "event_state": "England",
                "event_country": "United Kingdom",
                "event_location": "London, England, United Kingdom",
                "event_location_standardized": "London, England",
            }
        ]
    )
    lookup = build_location_lookup(location_info)
    assert lookup["london, united kingdom"] == "107"


def test_dedupe_location_info_merges_duplicate_cities():
    results = pd.DataFrame({"location_id": ["130", "107", "164"]})
    locations = pd.DataFrame(
        [
            {
                "location_id": "107",
                "event_city": "London",
                "event_state": "",
                "event_country": "United Kingdom",
                "event_location": "London, United Kingdom",
            },
            {
                "location_id": "130",
                "event_city": "London",
                "event_state": "England",
                "event_country": "United Kingdom",
                "event_location": "London, England, United Kingdom",
            },
            {
                "location_id": "164",
                "event_city": "London",
                "event_state": "England",
                "event_country": "United Kingdom",
                "event_location": "London, England, United Kingdom",
            },
        ]
    )
    out_results, out_locations, merged = dedupe_location_info(results, locations)
    assert merged == 2
    assert len(out_locations) == 1
    assert out_locations.loc[0, "location_id"] == "107"
    assert set(out_results["location_id"]) == {"107"}

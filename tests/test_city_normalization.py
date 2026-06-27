"""Tests for city display normalization."""

import pandas as pd

from transform.geography.city import (
    apply_city_normalization_to_frame,
    normalize_city_display,
    normalize_city_field,
    split_embedded_us_state_from_city,
    sync_export_city_columns,
)
from transform.data_preprocessing import normalize_geography


def test_normalize_city_display_all_caps():
    assert normalize_city_display("CHICAGO") == "Chicago"
    assert normalize_city_display("TOULOUSE") == "Toulouse"


def test_split_embedded_us_state_from_city():
    city, state = split_embedded_us_state_from_city("WILMINGTON DEL")
    assert city == "WILMINGTON"
    assert state == "Delaware"

    city, state = split_embedded_us_state_from_city("Phoenix AZ")
    assert city == "Phoenix"
    assert state == "Arizona"

    city, state = normalize_city_field("WILMINGTON DEL")
    assert city == "Wilmington"
    assert state == "Delaware"


def test_normalize_city_strips_trailing_comma():
    assert normalize_city_field("Milan,")[0] == "Milan"


def test_normalize_geography_fixes_shouty_cities():
    df = pd.DataFrame(
        [
            {
                "location_id": 104,
                "event_city": "CHICAGO",
                "event_state": "Illinois",
                "event_country": "United States",
                "event_location": "CHICAGO, IL, United States",
                "latitude": "41.88325",
                "longitude": "-87.6323879",
            },
            {
                "location_id": 108,
                "event_city": "WILMINGTON DEL",
                "event_state": "Delaware",
                "event_country": "United States",
                "event_location": "WILMINGTON DEL, Delaware, United States",
                "latitude": "39.744655",
                "longitude": "-75.5483909",
            },
        ]
    )
    out = normalize_geography(df)
    assert out.loc[0, "event_city"] == "Chicago"
    assert out.loc[0, "event_location"] == "Chicago, IL, United States"
    assert out.loc[1, "event_city"] == "Wilmington"
    assert out.loc[1, "event_location"] == "Wilmington, DE, United States"


def test_sync_export_city_columns_updates_editions(tmp_path):
    location = pd.DataFrame(
        [
            {
                "location_id": 104,
                "event_city": "Chicago",
                "event_state": "Illinois",
                "event_country": "United States",
                "event_location": "Chicago, IL, United States",
                "event_location_standardized": "Chicago, IL",
            }
        ]
    )
    location.to_csv(tmp_path / "location_info.csv", index=False)
    editions = pd.DataFrame(
        [
            {
                "edition_id": 1,
                "event_id": 125,
                "location_id": 104,
                "place_city": "CHICAGO",
                "place_state": "Illinois",
                "place_country": "United States",
                "location_raw": "CHICAGO, IL, United States",
                "typical_location": "CHICAGO, IL, United States",
            }
        ]
    )
    editions.to_csv(tmp_path / "event_editions.csv", index=False)

    updates = sync_export_city_columns(tmp_path)

    synced = pd.read_csv(tmp_path / "event_editions.csv")
    assert synced.loc[0, "place_city"] == "Chicago"
    assert synced.loc[0, "location_raw"] == "Chicago, IL, United States"
    assert updates["event_editions.csv"] > 0

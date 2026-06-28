"""Tests for city display normalization."""

import pandas as pd

from transform.geography.city import (
    apply_city_normalization_to_frame,
    normalize_city_display,
    normalize_city_field,
    normalize_location_whitespace,
    split_embedded_us_state_from_city,
    sync_export_city_columns,
    sync_upcoming_location_string,
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


def test_sync_upcoming_location_preserves_different_venue():
    result = sync_upcoming_location_string(
        "Madrid, Spain",
        "Madrid, Madrid, Spain",
        string_replacements={},
    )
    assert result == "Madrid, Spain"


def test_sync_upcoming_location_fixes_case_only_mismatch():
    result = sync_upcoming_location_string(
        "st. petersburg, russia",
        "St. Petersburg, Russia",
        string_replacements={},
    )
    assert result == "St. Petersburg, Russia"


def test_sync_upcoming_location_applies_known_replacement():
    result = sync_upcoming_location_string(
        "MOSCOW,  RUSSIA",
        "St. Petersburg, Russia",
        string_replacements={"MOSCOW, RUSSIA": "Moscow, Russia"},
    )
    assert result == "Moscow, Russia"


def test_sync_export_preserves_scheduled_location_raw(tmp_path):
    catalog = pd.DataFrame(
        [
            {
                "event_id": 347,
                "typical_location": "Madrid, Madrid, Spain",
                "upcoming_location": "Madrid, Spain",
            }
        ]
    )
    catalog.to_csv(tmp_path / "event_catalog.csv", index=False)
    scheduled = pd.DataFrame(
        [
            {
                "canonical_event_id": 347,
                "location_raw": "Madrid, Spain",
            }
        ]
    )
    scheduled.to_csv(tmp_path / "scheduled_events.csv", index=False)
    (tmp_path / "location_info.csv").write_text("location_id,event_city\n", encoding="utf-8")

    sync_export_city_columns(tmp_path)

    out = pd.read_csv(tmp_path / "scheduled_events.csv")
    assert out.loc[0, "location_raw"] == "Madrid, Spain"


def test_normalize_location_whitespace():
    assert normalize_location_whitespace("Moscow,  Russia") == "Moscow, Russia"


def test_sync_editions_preserves_typical_location(tmp_path):
    """Edition-level typical_location is export metadata; not overwritten from location_info."""
    location_info = pd.DataFrame(
        [
            {
                "location_id": 170,
                "event_city": "Madrid",
                "event_state": "",
                "event_country": "Spain",
                "event_location": "Madrid, Madrid, Spain",
            }
        ]
    )
    location_info.to_csv(tmp_path / "location_info.csv", index=False)
    editions = pd.DataFrame(
        [
            {
                "event_id": 347,
                "event_year": 2025,
                "event_month": 3,
                "location_id": 170,
                "place_city": "Madrid",
                "location_raw": "Madrid, Spain",
                "typical_location": "Madrid, Spain",
            }
        ]
    )
    editions.to_csv(tmp_path / "event_editions.csv", index=False)

    sync_export_city_columns(tmp_path)

    out = pd.read_csv(tmp_path / "event_editions.csv")
    assert out.loc[0, "location_raw"] == "Madrid, Madrid, Spain"
    assert out.loc[0, "typical_location"] == "Madrid, Spain"

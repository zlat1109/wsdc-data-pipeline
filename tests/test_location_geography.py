"""Tests for US state parsing and city-level coordinate canonicalization."""

import pandas as pd

from transform.data_preprocessing import (
    canonicalize_city_coordinates,
    location_city_key,
    normalize_geography,
    parse_us_state_from_location_text,
)


def test_parse_us_state_from_full_name_duplicate():
    assert parse_us_state_from_location_text("Burbank, California, California, USA") == "California"


def test_parse_us_state_from_city_code():
    assert parse_us_state_from_location_text("Phoenix, AZ, United States") == "Arizona"


def test_normalize_geography_fills_burbank_state():
    df = pd.DataFrame(
        [{
            "location_id": "54",
            "event_city": "Burbank",
            "event_state": "",
            "event_country": "United States",
            "latitude": "34.1820605",
            "longitude": "-118.3074827",
            "event_location": "Burbank, California, California, USA",
        }]
    )
    out = normalize_geography(df)
    assert out.loc[0, "event_state"] == "California"
    assert out.loc[0, "event_location"] == "Burbank, CA, United States"


def test_location_city_key_us_uses_state():
    row = pd.Series({
        "event_city": "Burlington",
        "event_country": "United States",
        "event_state": "Massachusetts",
    })
    assert location_city_key(row) == ("Burlington", "United States", "Massachusetts")


def test_canonicalize_collapses_london_suburb():
    df = pd.DataFrame([
        {
            "location_id": "107",
            "event_city": "London",
            "event_state": "England",
            "event_country": "United Kingdom",
            "latitude": 51.5072178,
            "longitude": -0.1275862,
            "event_location": "London, United Kingdom",
        },
        {
            "location_id": "130",
            "event_city": "London",
            "event_state": "England",
            "event_country": "United Kingdom",
            "latitude": 51.5077194,
            "longitude": -0.4726768,
            "event_location": "London, West Drayton, United Kingdom",
        },
    ])
    out = canonicalize_city_coordinates(df)
    assert out.loc[1, "latitude"] == 51.5072178
    assert out.loc[1, "longitude"] == -0.1275862


def test_canonicalize_keeps_burlington_ma_and_vt_separate():
    df = pd.DataFrame([
        {
            "location_id": "79",
            "event_city": "Burlington",
            "event_state": "Massachusetts",
            "event_country": "United States",
            "latitude": 42.5047161,
            "longitude": -71.1956205,
            "event_location": "Burlington, MA",
        },
        {
            "location_id": "144",
            "event_city": "Burlington",
            "event_state": "Vermont",
            "event_country": "United States",
            "latitude": 44.4758825,
            "longitude": -73.212072,
            "event_location": "Burlington, VT",
        },
    ])
    out = canonicalize_city_coordinates(df)
    assert out.loc[0, "latitude"] == 42.5047161
    assert out.loc[1, "latitude"] == 44.4758825


def test_canonicalize_washington_md_suburb_to_dc_center():
    df = pd.DataFrame([
        {
            "location_id": "13",
            "event_city": "Washington",
            "event_state": "District of Columbia",
            "event_country": "United States",
            "latitude": 38.9072873,
            "longitude": -77.0369274,
            "event_location": "Washington DC, USA",
        },
        {
            "location_id": "165",
            "event_city": "Washington",
            "event_state": "District of Columbia",
            "event_country": "United States",
            "latitude": 39.1289725,
            "longitude": -77.3783789,
            "event_location": "Washington DC, MD, USA",
        },
    ])
    out = canonicalize_city_coordinates(df)
    assert out.loc[1, "latitude"] == 38.9072873
    assert out.loc[1, "longitude"] == -77.0369274

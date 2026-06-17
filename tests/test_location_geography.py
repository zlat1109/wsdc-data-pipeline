"""Tests for US state parsing in location_info normalization."""

import pandas as pd

from transform.data_preprocessing import (
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

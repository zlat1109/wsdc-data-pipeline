"""Tests for Albany / US location fixes in points preprocess."""

import pandas as pd

from transform.data_preprocessing import normalize_geography


def test_albany_location_id_161_gets_state():
    df = pd.DataFrame(
        [
            {
                "location_id": 161,
                "event_city": "Albany",
                "event_state": None,
                "event_country": "United States",
                "event_location": "Albany, NY, Albany",
            }
        ]
    )
    out = normalize_geography(df)
    row = out.iloc[0]
    assert row["event_state"] == "New York"
    assert row["event_location"] == "Albany, NY"
    assert row["event_location_standardized"] == "Albany, NY"

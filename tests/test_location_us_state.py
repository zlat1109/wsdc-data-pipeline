"""Tests for Albany / US location fixes in points preprocess."""

import pandas as pd

from transform.data_preprocessing import normalize_geography
from transform.knowledge.locations import (
    LOCATION_ID_CORRECTIONS,
    LOCATION_ID_MERGE_MAP,
)


def test_albany_gets_state_and_full_location():
    df = pd.DataFrame(
        [
            {
                "location_id": 139,
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
    assert row["event_location"] == "Albany, NY, United States"
    assert row["event_location_standardized"] == "Albany, NY"


def test_stale_albany_id_merges_into_canonical_row():
    assert LOCATION_ID_MERGE_MAP["161"] == "139"
    assert 161 not in LOCATION_ID_CORRECTIONS
    assert LOCATION_ID_CORRECTIONS[139]["event_city"] == "Albany"

"""Tests for Singapore location_id consolidation."""

import pandas as pd

from transform.geography.resolve import build_location_lookup, consolidate_location_ids
from transform.knowledge.locations import (
    LOCATION_ID_MERGE_MAP,
    LOCATION_STRING_ALIASES,
    SINGAPORE_CANONICAL_LOCATION_ID,
)


def test_build_location_lookup_includes_singapore_aliases():
    location_info = pd.DataFrame(
        [
            {
                "location_id": "159",
                "event_location": "Singapore, Singapore",
                "event_location_standardized": "Singapore, Singapore",
            }
        ]
    )
    lookup = build_location_lookup(location_info)
    assert lookup["singapore, singapore"] == "159"
    assert lookup["singapore"] == str(SINGAPORE_CANONICAL_LOCATION_ID)
    assert lookup["singapore, singapore, singapore"] == str(SINGAPORE_CANONICAL_LOCATION_ID)


def test_build_location_lookup_includes_venue_aliases():
    lookup = build_location_lookup(pd.DataFrame())
    assert lookup["boston club, germany"] == "127"
    assert lookup["amsterdam, netherlands"] == "191"
    assert lookup["london, england, united kingdom"] == "107"
    assert lookup["north myrtle beach, sc, united states"] == "325"
    assert lookup["n. myrtle beach, sc, united states"] == "325"


def test_consolidate_location_ids_merges_duplicate_singapore_rows():
    results = pd.DataFrame({"location_id": ["350", "159", "350"]})
    locations = pd.DataFrame(
        {
            "location_id": ["159", "244", "350"],
            "event_location": [
                "Singapore, Singapore",
                "Singapore, Singapore",
                "Singapore, Singapore",
            ],
        }
    )
    out_results, out_locations = consolidate_location_ids(results, locations)
    assert out_results["location_id"].tolist() == ["159", "159", "159"]
    assert set(out_locations["location_id"].astype(str)) == {"159"}
    assert "350" in LOCATION_ID_MERGE_MAP

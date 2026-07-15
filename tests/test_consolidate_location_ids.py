"""Tests for location_id consolidation and WSDC location aliases."""

import pandas as pd

from transform.geography.resolve import (
    build_location_lookup,
    consolidate_location_ids,
    resolve_result_location_ids,
)
from transform.knowledge.locations import (
    LOCATION_ID_MERGE_MAP,
    SAN_ANTONIO_CANONICAL_LOCATION_ID,
    SINGAPORE_CANONICAL_LOCATION_ID,
)
from transform.preprocess_with_log import preprocess_with_log


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
    assert lookup["ft. lauderdale, fl, united states"] == "55"
    assert lookup["anaheim/garden grove, ca, united states"] == "23"
    assert lookup["washington, md, united states"] == "353"
    assert lookup["silver spring, md, united states"] == "353"


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


def test_build_location_lookup_includes_san_antonio_alias():
    location_info = pd.DataFrame(
        [
            {
                "location_id": "167",
                "event_city": "San Antonio",
                "event_state": "Texas",
                "event_country": "United States",
                "event_location": "San Antonio, TX, United States",
                "event_location_standardized": "San Antonio, TX",
            }
        ]
    )
    lookup = build_location_lookup(location_info)
    assert lookup["san antonio, texas, united states"] == str(SAN_ANTONIO_CANONICAL_LOCATION_ID)


def test_resolve_swing_crush_location_uses_canonical_san_antonio_id():
    location_info = pd.DataFrame(
        [
            {
                "location_id": "167",
                "event_city": "San Antonio",
                "event_state": "Texas",
                "event_country": "United States",
                "latitude": "29.4251905",
                "longitude": "-98.4945922",
                "event_location": "San Antonio, TX, United States",
                "event_location_standardized": "San Antonio, TX",
                "coordinates_valid": "t",
            }
        ]
    )
    results = pd.DataFrame(
        [
            {
                "dancer_id": "1",
                "event_name": "Swing Crush",
                "event_location": "San antonio, Texas, United states",
                "location_id": "",
            }
        ]
    )
    out_results, out_locations = resolve_result_location_ids(results, location_info)
    assert out_results.loc[0, "location_id"] == "167"
    assert len(out_locations) == 1


def test_consolidate_location_ids_merges_san_antonio_duplicate():
    results = pd.DataFrame({"location_id": ["445", "167", "445"]})
    locations = pd.DataFrame(
        {
            "location_id": ["167", "445"],
            "event_location": [
                "San Antonio, TX, United States",
                "San antonio, Texas, United states",
            ],
        }
    )
    out_results, out_locations = consolidate_location_ids(results, locations)
    assert out_results["location_id"].tolist() == ["167", "167", "167"]
    assert set(out_locations["location_id"].astype(str)) == {"167"}
    assert "445" in LOCATION_ID_MERGE_MAP


def test_preprocess_merges_swing_crush_san_antonio_duplicate():
    raw = {
        "location_info": pd.DataFrame(
            [
                {
                    "location_id": "167",
                    "event_city": "San Antonio",
                    "event_state": "Texas",
                    "event_country": "United States",
                    "latitude": "29.4251905",
                    "longitude": "-98.4945922",
                    "event_location": "San Antonio, TX, United States",
                    "event_location_standardized": "San Antonio, TX",
                    "coordinates_valid": "t",
                },
                {
                    "location_id": "445",
                    "event_city": "San antonio",
                    "event_state": "",
                    "event_country": "United states",
                    "latitude": "",
                    "longitude": "",
                    "event_location": "San antonio, Texas, United states",
                    "event_location_standardized": "San antonio, Texas, United states",
                    "coordinates_valid": "",
                },
            ]
        ),
        "dancers_results_info": pd.DataFrame(
            [
                {
                    "dancer_id": "1",
                    "event_name": "Swing Crush",
                    "event_location": "San antonio, Texas, United states",
                    "location_id": "445",
                    "event_competition": "Novice",
                    "event_role": "leader",
                    "event_result": "1",
                    "event_points": "10",
                    "event_dance": "West Coast Swing",
                    "event_year": "2026",
                    "event_month": "2",
                    "event_year_and_month": "2026-02-01",
                }
            ]
        ),
    }
    processed, _tracker = preprocess_with_log(raw)
    assert processed["dancers_results_info"].loc[0, "location_id"] == "167"
    assert "445" not in set(processed["location_info"]["location_id"].astype(str))
    row = processed["location_info"].loc[
        processed["location_info"]["location_id"].astype(str) == "167"
    ].iloc[0]
    assert row["event_city"] == "San Antonio"
    assert row["event_state"] == "Texas"
    assert row["event_country"] == "United States"


def test_consolidate_location_ids_merges_boston_club_duplicate():
    results = pd.DataFrame({"location_id": ["436", "127", "436"]})
    locations = pd.DataFrame(
        {
            "location_id": ["127", "436"],
            "event_location": [
                "Düsseldorf, Germany",
                "Boston Club, Germany",
            ],
            "latitude": ["51.2230411", ""],
            "longitude": ["6.7824545", ""],
        }
    )
    out_results, out_locations = consolidate_location_ids(results, locations)
    assert out_results["location_id"].tolist() == ["127", "127", "127"]
    assert set(out_locations["location_id"].astype(str)) == {"127"}
    assert "436" in LOCATION_ID_MERGE_MAP

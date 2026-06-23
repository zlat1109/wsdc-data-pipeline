"""Tests for preprocess with logging."""

import pandas as pd

from transform.preprocess_tracker import PreprocessTracker
from transform.preprocess_with_log import (
    _apply_auto_strip_event_year,
    _apply_mapping,
    preprocess_with_log,
)
from transform.preprocess_with_log import build_combined_report  # noqa: F401


def test_auto_strip_event_year_tracked():
    df = pd.DataFrame({"event_name": ["Baltic Swing", "New Event 2026", "Boogie By The Bay"]})
    tracker = PreprocessTracker()
    out = _apply_auto_strip_event_year(df, "event_name", table="t", tracker=tracker)
    assert out.loc[1, "event_name"] == "New Event"
    assert len(tracker.rules) == 1
    assert tracker.rules[0].rule_id == "AUTO_STRIP_EVENT_YEAR"


def test_known_map_tracked():
    df = pd.DataFrame({"event_name": ["BALTIC SWING", "BALTIC SWING", "Other"]})
    tracker = PreprocessTracker()
    from transform.knowledge import EVENT_NAME_NORMALIZATION

    out = _apply_mapping(
        df,
        "event_name",
        EVENT_NAME_NORMALIZATION,
        table="t",
        rule_id="EVENT_NAME_NORMALIZATION",
        tracker=tracker,
    )
    assert out["event_name"].tolist()[0] == "Baltic Swing"
    assert tracker.rules[0].rows_affected == 2


def test_phoenix_july_maps_to_convention():
    df = pd.DataFrame({"event_name": ["Phoenix 4th of July", "4TH of July Convention"]})
    tracker = PreprocessTracker()
    from transform.knowledge import EVENT_NAME_NORMALIZATION

    out = _apply_mapping(
        df,
        "event_name",
        EVENT_NAME_NORMALIZATION,
        table="t",
        rule_id="EVENT_NAME_NORMALIZATION",
        tracker=tracker,
    )
    assert out["event_name"].tolist() == ["4TH of July Convention", "4TH of July Convention"]
    assert tracker.rules[0].rows_affected == 1


def test_combined_report_sections():
    raw = {
        "dancers_results_info": pd.DataFrame(
            {
                "event_name": ["BALTIC SWING", "Mystery Event 2026"],
                "event_competition": ["Advanced", "Novice"],
                "event_role": ["leader", "follower"],
                "location_id": ["1", "2"],
                "dancer_id": ["1", "2"],
            }
        ),
        "dancer_role_info": pd.DataFrame({"dancer_id": ["1", "2"], "dancer_name": ["A", "B"]}),
    }
    processed, tracker = preprocess_with_log({k: v.copy() for k, v in raw.items()})
    report = build_combined_report(
        {k: v.copy() for k, v in raw.items()},
        processed,
        tracker,
    )
    assert "before_processing" in report
    assert "applied_normalizations" in report
    assert "manual_review_required" in report
    assert report["summary"]["applied_rules_count"] >= 1


def test_preprocess_canonicalizes_london_suburb_coords():
    raw = {
        "location_info": pd.DataFrame([
            {
                "location_id": "107",
                "event_city": "London",
                "event_state": "England",
                "event_country": "United Kingdom",
                "latitude": "51.5072178",
                "longitude": "-0.1275862",
                "event_location": "London, United Kingdom",
            },
            {
                "location_id": "130",
                "event_city": "London",
                "event_state": "England",
                "event_country": "United Kingdom",
                "latitude": "51.5077194",
                "longitude": "-0.4726768",
                "event_location": "London, West Drayton, United Kingdom",
            },
        ]),
    }
    processed, tracker = preprocess_with_log(raw)
    assert processed["location_info"].loc[1, "latitude"] == "51.5072178"
    assert processed["location_info"].loc[1, "longitude"] == "-0.1275862"
    canon_rules = [r for r in tracker.rules if r.rule_id == "CITY_CANONICAL_COORDINATES"]
    assert canon_rules and canon_rules[0].rows_affected >= 1

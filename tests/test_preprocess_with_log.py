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
    from transform.data_preprocessing import EVENT_NAME_NORMALIZATION

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

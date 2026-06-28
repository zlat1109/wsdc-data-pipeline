"""Tests for MERGE_EVENT_ID_MAP preprocess helper."""

import pandas as pd

from transform.knowledge.merge_map import apply_merge_event_id_map
from transform.preprocess_tracker import PreprocessTracker


def test_apply_merge_event_id_map_noop_without_column():
    df = pd.DataFrame({"event_name": ["SwingTime"]})
    out = apply_merge_event_id_map(df)
    assert out.equals(df)


def test_apply_merge_event_id_map_without_tracker():
    df = pd.DataFrame({"event_name_id": [66]})
    out = apply_merge_event_id_map(df)
    assert out.loc[0, "event_name_id"] == 47


def test_apply_merge_event_id_map_records_tracker():
    df = pd.DataFrame({"event_name_id": [66, 66]})
    tracker = PreprocessTracker()
    apply_merge_event_id_map(df, tracker=tracker)
    assert any(r.rule_id == "MERGE_EVENT_ID_MAP" and r.rows_affected == 2 for r in tracker.rules)

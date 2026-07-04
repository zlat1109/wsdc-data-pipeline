"""Tests for backfill_empty_result_event_locations."""

import pandas as pd

from transform.knowledge.apply import backfill_empty_result_event_locations


def test_backfill_scandinavian_open_from_event_id():
    df = pd.DataFrame(
        {
            "event_name_id": ["229"],
            "event_name": ["Scandinavian Open"],
            "event_location": [""],
        }
    )
    out = backfill_empty_result_event_locations(df)
    assert out.loc[0, "event_location"] == "Stockholm, Sweden"


def test_backfill_scandinavian_open_from_event_name_only():
    df = pd.DataFrame(
        {
            "event_name": ["Scandinavian Open"],
            "event_location": [""],
        }
    )
    out = backfill_empty_result_event_locations(df)
    assert out.loc[0, "event_location"] == "Stockholm, Sweden"

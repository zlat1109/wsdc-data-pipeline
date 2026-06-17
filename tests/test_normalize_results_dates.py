"""Tests for dancers_results_info date normalization."""

import pandas as pd

from transform.data_preprocessing import normalize_results_dates, results_date_parse_rate
from transform.preprocess_with_log import preprocess_with_log


def test_cloud_parse_month_year_format():
    df = pd.DataFrame(
        {
            "dancer_id": ["1", "2"],
            "event_year": ["", ""],
            "event_month": ["", ""],
            "event_year_and_month": ["January 1997", "October 1994"],
            "event_role": ["leader", "follower"],
        }
    )
    out = normalize_results_dates(df)
    assert out.loc[0, "event_year"] == "1997"
    assert out.loc[0, "event_month"] == "1"
    assert out.loc[0, "event_year_and_month"] == "1997-01-01"
    assert out.loc[1, "event_year"] == "1994"
    assert out.loc[1, "event_month"] == "10"
    assert out.loc[1, "event_year_and_month"] == "1994-10-01"


def test_already_normalized_local_format_unchanged():
    df = pd.DataFrame(
        {
            "dancer_id": ["1"],
            "event_year": ["2003"],
            "event_month": ["7"],
            "event_year_and_month": ["2003-07-01"],
            "event_role": ["leader"],
        }
    )
    out = normalize_results_dates(df)
    assert out.loc[0, "event_year"] == "2003"
    assert out.loc[0, "event_month"] == "7"
    assert out.loc[0, "event_year_and_month"] == "2003-07-01"


def test_results_date_parse_rate_on_cloud_format():
    df = pd.DataFrame(
        {
            "event_year": [""],
            "event_month": [""],
            "event_year_and_month": ["July 1993"],
        }
    )
    assert results_date_parse_rate(df) == 1.0


def test_preprocess_with_log_normalizes_results_dates():
    raw = {
        "dancers_results_info": pd.DataFrame(
            {
                "dancer_id": ["1"],
                "event_name": ["Monterey SwingFest"],
                "event_competition": ["Novice"],
                "event_role": ["leader"],
                "location_id": ["1"],
                "event_year": [""],
                "event_month": [""],
                "event_year_and_month": ["January 1997"],
            }
        ),
    }
    processed, _ = preprocess_with_log({k: v.copy() for k, v in raw.items()})
    out = processed["dancers_results_info"]
    assert out.loc[0, "event_year"] == "1997"
    assert out.loc[0, "event_month"] == "1"
    assert out.loc[0, "event_year_and_month"] == "1997-01-01"

"""Tests for data quality audit checks."""

import pandas as pd

from transform.quality_audit import (
    check_event_name_variants,
    check_event_name_year_suffix,
    check_location_format,
    strip_event_year,
)


def test_strip_event_year():
    assert strip_event_year("Scandinavian Open WCS 2022") == "Scandinavian Open WCS"


def test_event_name_year_suffix():
    df = pd.DataFrame(
        {"event_name": ["Baltic Swing", "Scandinavian Open 2024", "Boogie By The Bay"]}
    )
    finding = check_event_name_year_suffix(df)
    assert finding is not None
    assert finding.code == "EVENT_NAME_YEAR_SUFFIX"
    assert finding.count == 1


def test_event_name_variants():
    df = pd.DataFrame(
        {
            "event_name": [
                "BALTIC SWING",
                "Baltic Swing",
                "Boogie By The Bay",
            ]
        }
    )
    finding = check_event_name_variants(df)
    assert finding is not None
    assert finding.code == "EVENT_NAME_VARIANTS"


def test_location_city_equals_country():
    df = pd.DataFrame(
        {
            "location_id": ["1"],
            "event_city": ["Albany"],
            "event_country": ["Albany"],
            "event_location": ["Albany"],
        }
    )
    findings = check_location_format(df)
    codes = {f.code for f in findings}
    assert "LOCATION_CITY_EQUALS_COUNTRY" in codes

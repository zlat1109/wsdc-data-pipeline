"""events_wsdc.location must follow EVENT_NAME_LOCATION_OVERRIDES."""

from __future__ import annotations

import pandas as pd

from transform.knowledge.apply import force_events_wsdc_locations_from_event_name_overrides
from transform.preprocess_with_log import preprocess_with_log


def test_force_events_wsdc_remaps_wrong_location_string(monkeypatch):
    overrides = {"Dance Jam Jack & Jill Weekend": "Silver Spring, MD, United States"}
    monkeypatch.setattr(
        "transform.knowledge.apply.EVENT_NAME_LOCATION_OVERRIDES", overrides
    )
    df = pd.DataFrame(
        [
            {
                "name": "Dance Jam Jack & Jill Weekend",
                "location": "Jeju, Republic of Korea",
            },
            {
                "name": "Korea Westival",
                "location": "Jeju, Republic of Korea",
            },
        ]
    )
    out, changed = force_events_wsdc_locations_from_event_name_overrides(df)
    assert changed == 1
    assert out.loc[0, "location"] == "Silver Spring, MD, United States"
    assert out.loc[1, "location"] == "Jeju, Republic of Korea"


def test_preprocess_applies_events_wsdc_location_overrides():
    raw = {
        "events_wsdc": pd.DataFrame(
            [
                {
                    "name": "Dance Jam Jack & Jill Weekend",
                    "location": "Jeju, Republic of Korea",
                    "url": "http://example.com",
                    "event_year": "2026",
                    "event_month": "5",
                    "event_year_month": "2026-05",
                }
            ]
        ),
        "location_info": pd.DataFrame(
            [
                {
                    "location_id": "353",
                    "event_city": "Silver Spring",
                    "event_state": "Maryland",
                    "event_country": "United States",
                    "event_location": "Silver Spring, MD, United States",
                    "event_location_standardized": "Silver Spring, MD",
                    "latitude": "38.99",
                    "longitude": "-77.02",
                    "coordinates_valid": "t",
                }
            ]
        ),
    }
    processed, tracker = preprocess_with_log(raw)
    assert (
        processed["events_wsdc"].loc[0, "location"]
        == "Silver Spring, MD, United States"
    )
    assert any(
        r.rule_id == "EVENT_NAME_LOCATION_OVERRIDE" and r.table == "events_wsdc"
        for r in tracker.rules
    )

"""Tests for event_knowledge location patches."""

import pandas as pd

from transform.event_knowledge import apply_event_location_patches


def test_scandinavian_location_patch_uses_event_id_not_hardcoded_location_id():
    location_info = pd.DataFrame(
        [
            {"location_id": 999, "event_city": "", "event_country": "", "event_location": ""},
            {"location_id": 222, "event_city": "St. Petersburg", "event_country": "Russia", "event_location": "St. Petersburg, Russia"},
        ]
    )
    results = pd.DataFrame(
        [
            {"event_name_id": 229, "event_name": "Scandinavian Open", "location_id": 999},
            {"event_name_id": 215, "event_name": "Swing & Snow", "location_id": 222},
        ]
    )
    patched = apply_event_location_patches(location_info, results)
    row = patched.loc[patched["location_id"] == 999].iloc[0]
    assert row["event_city"] == "Stockholm"
    assert row["event_location"] == "Stockholm, Sweden"
    swing = patched.loc[patched["location_id"] == 222].iloc[0]
    assert swing["event_city"] == "St. Petersburg"

"""Tests for forced EVENT_NAME_LOCATION_OVERRIDES location_id remaps."""

import pandas as pd

from transform.knowledge.apply import force_result_locations_from_event_name_overrides


def test_force_sweden_westie_gala_off_wailea():
    location_info = pd.DataFrame(
        [
            {
                "location_id": "124",
                "event_city": "Wailea",
                "event_state": "Hawaii",
                "event_country": "United States",
                "event_location": "Wailea, HI, United States",
            },
            {
                "location_id": "199",
                "event_city": "Stockholm",
                "event_state": "",
                "event_country": "Sweden",
                "event_location": "Stockholm, Sweden",
            },
            {
                "location_id": "355",
                "event_city": "Wailea",
                "event_state": "Hawaii",
                "event_country": "United States",
                "event_location": "Wailea, HI, United States",
            },
        ]
    )
    results = pd.DataFrame(
        [
            {
                "event_name": "Sweden Westie Gala",
                "location_id": "124",
                "event_location": "Wailea, HI, United States",
            },
            {
                "event_name": "The Aloha Open",
                "location_id": "124",
                "event_location": "Wailea, HI, United States",
            },
            {
                "event_name": "Swedish Swing Summer Camp",
                "location_id": "124",
                "event_location": "",
            },
        ]
    )

    out, changed = force_result_locations_from_event_name_overrides(results, location_info)

    assert changed == 2
    sweden = out.loc[out["event_name"] == "Sweden Westie Gala"].iloc[0]
    assert str(sweden["location_id"]) == "199"
    assert sweden["event_location"] == "Stockholm, Sweden"

    camp = out.loc[out["event_name"] == "Swedish Swing Summer Camp"].iloc[0]
    assert str(camp["location_id"]) == "199"
    assert camp["event_location"] == "Stockholm, Sweden"

    # Aloha Open must keep Wailea — do not rewrite shared location_id geography.
    aloha = out.loc[out["event_name"] == "The Aloha Open"].iloc[0]
    assert str(aloha["location_id"]) == "124"


def test_force_french_connection_to_annecy():
    location_info = pd.DataFrame(
        [
            {
                "location_id": "13",
                "event_city": "Washington",
                "event_state": "District of Columbia",
                "event_country": "United States",
                "event_location": "Washington, DC, United States",
            },
            {
                "location_id": "188",
                "event_city": "Annecy",
                "event_state": "",
                "event_country": "France",
                "event_location": "Annecy, France",
            },
        ]
    )
    results = pd.DataFrame(
        [
            {
                "event_name": "FRENCH CONNECTION WCS",
                "location_id": "13",
                "event_location": "Washington, DC, United States",
            }
        ]
    )
    out, changed = force_result_locations_from_event_name_overrides(results, location_info)
    assert changed == 1
    assert str(out.loc[0, "location_id"]) == "188"
    assert out.loc[0, "event_location"] == "Annecy, France"

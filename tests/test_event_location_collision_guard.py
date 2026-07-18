"""Regression guards for shared/wrong location_id collisions."""

import pandas as pd

from transform.geography.constants import COUNTRY_STANDARDIZATION
from transform.geography.event_location_guard import find_name_location_country_conflicts
from transform.geography.normalize import standardize_country
from transform.knowledge.apply import force_result_locations_from_event_name_overrides
from transform.knowledge.locations import LOCATION_ID_MERGE_MAP
from transform.quality_audit import check_event_name_location_country_conflicts


def _collision_fixture() -> tuple[pd.DataFrame, pd.DataFrame]:
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
                "event_name": "Sweden Westie Gala",
                "location_id": "124",
                "dancer_id": "18215",
                "event_role": "follower",
                "event_points": "10",
            },
            {
                "event_name": "Swedish Swing Summer Camp",
                "location_id": "124",
                "dancer_id": "1",
                "event_role": "leader",
                "event_points": "1",
            },
            {
                "event_name": "The Aloha Open",
                "location_id": "124",
                "dancer_id": "2",
                "event_role": "leader",
                "event_points": "1",
            },
            {
                "event_name": "FRENCH CONNECTION WCS",
                "location_id": "13",
                "dancer_id": "3",
                "event_role": "leader",
                "event_points": "1",
            },
        ]
    )
    return results, location_info


def test_guard_detects_sweden_wailea_collision():
    results, locations = _collision_fixture()
    conflicts = find_name_location_country_conflicts(results, locations)
    names = {c.event_name for c in conflicts}
    assert "Sweden Westie Gala" in names
    assert "Swedish Swing Summer Camp" in names
    assert "FRENCH CONNECTION WCS" in names
    # Aloha Open is correctly in the US — must not be flagged.
    assert "The Aloha Open" not in names


def test_force_clears_known_collisions_for_fran_case():
    results, locations = _collision_fixture()
    before = find_name_location_country_conflicts(results, locations)
    assert before

    fixed, changed = force_result_locations_from_event_name_overrides(results, locations)
    assert changed >= 3

    after = find_name_location_country_conflicts(fixed, locations)
    assert after == []

    fran = fixed[
        (fixed["dancer_id"] == "18215") & (fixed["event_name"] == "Sweden Westie Gala")
    ].iloc[0]
    assert str(fran["location_id"]) == "199"

    aloha = fixed[fixed["event_name"] == "The Aloha Open"].iloc[0]
    assert str(aloha["location_id"]) == "124"


def test_quality_audit_emits_conflict_finding():
    results, locations = _collision_fixture()
    finding = check_event_name_location_country_conflicts(results, locations)
    assert finding is not None
    assert finding.code == "EVENT_NAME_LOCATION_COUNTRY_CONFLICT"
    assert finding.severity == "high"


def test_south_korea_aliases_to_republic_of_korea():
    assert standardize_country("South Korea") == "Republic of Korea"
    assert standardize_country("Korea, South") == "Republic of Korea"
    assert standardize_country("Korea") == "Republic of Korea"
    assert standardize_country("Republic of Korea") == "Republic of Korea"
    assert COUNTRY_STANDARDIZATION["South Korea"] == "Republic of Korea"


def test_jeju_south_korea_location_id_merges_to_canonical():
    assert LOCATION_ID_MERGE_MAP["395"] == "213"


def test_guard_detects_baltic_swing_phoenix_collision():
    location_info = pd.DataFrame(
        [
            {
                "location_id": "3",
                "event_city": "Phoenix",
                "event_country": "United States",
            },
            {
                "location_id": "186",
                "event_city": "Gdańsk",
                "event_country": "Poland",
            },
        ]
    )
    results = pd.DataFrame(
        [
            {"event_name": "Baltic Swing", "location_id": "3"},
            {"event_name": "Desert City Swing", "location_id": "3"},
        ]
    )
    conflicts = find_name_location_country_conflicts(results, location_info)
    names = {c.event_name for c in conflicts}
    assert "Baltic Swing" in names
    assert "Desert City Swing" not in names

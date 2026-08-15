"""Regression guards for shared/wrong location_id collisions."""

import pandas as pd

from transform.geography.constants import COUNTRY_STANDARDIZATION
from transform.geography.event_location_guard import (
    find_catalog_typical_upcoming_conflicts,
    find_name_location_country_conflicts,
    find_scheduled_country_conflicts,
)
from transform.geography.normalize import standardize_country
from transform.knowledge.apply import force_result_locations_from_event_name_overrides
from transform.knowledge.locations import LOCATION_ID_MERGE_MAP
from transform.quality_audit import (
    check_catalog_typical_vs_upcoming,
    check_event_name_location_country_conflicts,
    check_scheduled_vs_results_country,
)


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


def test_scheduled_country_conflict_catches_no_hint_events():
    """Sea Dance / Med in Swing pattern: no country token in name, calendar disagrees."""
    location_info = pd.DataFrame(
        [
            {"location_id": "127", "event_city": "Düsseldorf", "event_country": "Germany"},
            {"location_id": "3", "event_city": "Phoenix", "event_country": "United States"},
            {"location_id": "113", "event_city": "Moscow", "event_country": "Russia"},
        ]
    )
    results = pd.DataFrame(
        [
            {"event_name": "Sea Dance Fest", "location_id": "127"},
            {"event_name": "Med in Swing", "location_id": "3"},
            {"event_name": "Swing & Snow", "location_id": "113"},
        ]
    )
    scheduled = pd.DataFrame(
        [
            {
                "canonical_name": "Sea Dance Fest",
                "country": "Russia",
                "location_raw": "Moscow, Moscow region, Russia",
            },
            {
                "canonical_name": "Med in Swing",
                "country": "France",
                "location_raw": "La Londe-les-Maures, France",
            },
            {
                "canonical_name": "Swing & Snow",
                "country": "Russian Federation",
                "location_raw": "Saint Petersburg, Russia",
            },
        ]
    )

    conflicts = find_scheduled_country_conflicts(results, location_info, scheduled)
    names = {c.event_name for c in conflicts}
    assert names == {"Sea Dance Fest", "Med in Swing"}

    finding = check_scheduled_vs_results_country(results, location_info, scheduled)
    assert finding is not None
    assert finding.code == "SCHEDULED_VS_RESULTS_COUNTRY_CONFLICT"
    assert finding.severity == "high"


def test_scheduled_country_conflict_skips_known_series_moves():
    location_info = pd.DataFrame(
        [{"location_id": "13", "event_city": "Washington", "event_country": "United States"}]
    )
    results = pd.DataFrame([{"event_name": "Westie's Angels", "location_id": "13"}])
    scheduled = pd.DataFrame(
        [
            {
                "canonical_name": "Westie's Angels",
                "country": "France",
                "location_raw": "LYON, rhones, FRANCE",
            }
        ]
    )
    assert find_scheduled_country_conflicts(results, location_info, scheduled) == []


def test_catalog_typical_upcoming_conflict_detects_stuck_typical():
    catalog = pd.DataFrame(
        [
            {
                "canonical_name": "Freedom Swing Dance Challenge",
                "typical_location": "Venray, Netherlands",
                "upcoming_location": "WILMINGTON DEL, Delaware, United States",
                "typical_country": "Netherlands",
            },
            {
                "canonical_name": "USA Grand Nationals",
                "typical_location": "Atlanta, GA, United States",
                "upcoming_location": "Atlanta, GA United States",
                "typical_country": "United States",
            },
            {
                "canonical_name": "Swingside Invitational",
                "typical_location": "San Antonio, TX",
                "upcoming_location": "Liège, Belgium",
                "typical_country": "United States",
            },
        ]
    )
    conflicts = find_catalog_typical_upcoming_conflicts(catalog)
    names = {c.canonical_name for c in conflicts}
    # stuck typical flagged; US alias artefact and known series move skipped
    assert names == {"Freedom Swing Dance Challenge"}

    finding = check_catalog_typical_vs_upcoming(catalog)
    assert finding is not None
    assert finding.code == "CATALOG_TYPICAL_UPCOMING_CONFLICT"
    assert finding.severity == "medium"


def test_guard_detects_nz_open_st_petersburg_collision():
    location_info = pd.DataFrame(
        [
            {
                "location_id": "222",
                "event_city": "St. Petersburg",
                "event_country": "Russia",
            },
            {
                "location_id": "168",
                "event_city": "Auckland",
                "event_country": "New Zealand",
            },
        ]
    )
    results = pd.DataFrame(
        [
            {
                "event_name": "New Zealand Open Swing Dance Championships",
                "location_id": "222",
            },
            {"event_name": "Swing & Snow", "location_id": "222"},
        ]
    )
    conflicts = find_name_location_country_conflicts(results, location_info)
    names = {c.event_name for c in conflicts}
    assert "New Zealand Open Swing Dance Championships" in names
    assert "Swing & Snow" not in names


def test_guard_detects_berlin_and_saunaswing_collisions():
    location_info = pd.DataFrame(
        [
            {
                "location_id": "266",
                "event_city": "Brno",
                "event_country": "Czech Republic",
            },
            {
                "location_id": "124",
                "event_city": "Wailea",
                "event_country": "United States",
            },
        ]
    )
    results = pd.DataFrame(
        [
            {"event_name": "SwingLab Berlin", "location_id": "266"},
            {"event_name": "Berlin Swing Revolution", "location_id": "266"},
            {"event_name": "Swing Fiction", "location_id": "266"},
            {"event_name": "SaunaSwing", "location_id": "124"},
        ]
    )
    conflicts = find_name_location_country_conflicts(results, location_info)
    names = {c.event_name for c in conflicts}
    assert "SwingLab Berlin" in names
    assert "Berlin Swing Revolution" in names
    assert "SaunaSwing" in names
    assert "Swing Fiction" not in names


def test_event_id_canonical_mismatch_uniform_wrong_location():
    """All rows on one foreign location_id — name-collision audit is silent."""
    from transform.geography.event_location_guard import (
        find_event_id_canonical_location_mismatches,
    )
    from transform.quality_audit import check_event_id_canonical_location_mismatch

    location_info = pd.DataFrame(
        [
            {
                "location_id": "222",
                "event_city": "St. Petersburg",
                "event_country": "Russia",
            },
            {
                "location_id": "174",
                "event_city": "Melbourne",
                "event_country": "Australia",
            },
        ]
    )
    catalog = pd.DataFrame(
        [
            {
                "event_id": "385",
                "canonical_name": "Revitalise WCS",
                "typical_location": "St. Petersburg, Russia",
                "upcoming_location": "",
            }
        ]
    )
    results = pd.DataFrame(
        [
            {"event_name": "Revitalise WCS", "location_id": "222"},
            {"event_name": "Revitalise WCS", "location_id": "222"},
        ]
    )
    editions = pd.DataFrame(
        [
            {
                "event_id": "385",
                "event_name": "Revitalise WCS",
                "location_id": "222",
            }
        ]
    )
    known = {385: {"typical_location": "Melbourne, Australia"}}
    mismatches = find_event_id_canonical_location_mismatches(
        results,
        location_info,
        catalog,
        editions,
        known_metadata=known,
        name_overrides={},
    )
    assert len(mismatches) == 1
    m = mismatches[0]
    assert m.event_id == "385"
    assert m.canonical_source == "known"
    assert m.mismatch_side == "both"
    assert m.results_country == "russia"
    assert m.canonical_country == "australia"

    finding = check_event_id_canonical_location_mismatch(
        results, location_info, catalog, editions
    )
    # production KNOWN/overrides also cover Revitalise → still flags Russia vs Australia
    assert finding is not None
    assert finding.code == "EVENT_ID_CANONICAL_LOCATION_MISMATCH"
    assert finding.severity == "high"


def test_event_id_canonical_from_name_override_via_catalog():
    from transform.geography.event_location_guard import (
        find_event_id_canonical_location_mismatches,
    )

    location_info = pd.DataFrame(
        [
            {"location_id": "7", "event_city": "New York", "event_country": "United States"},
            {"location_id": "86", "event_city": "Montreal", "event_country": "Canada"},
        ]
    )
    catalog = pd.DataFrame(
        [
            {
                "event_id": "178",
                "canonical_name": "Montreal Westie Fest",
                "typical_location": "New York, NY",
                "upcoming_location": "Montreal, Quebec, Canada",
            }
        ]
    )
    results = pd.DataFrame(
        [{"event_name": "Montreal Westie Fest", "location_id": "7"}] * 3
    )
    mismatches = find_event_id_canonical_location_mismatches(
        results,
        location_info,
        catalog,
        known_metadata={},
        name_overrides={"Montreal Westie Fest": "Montreal, Canada"},
    )
    assert len(mismatches) == 1
    assert mismatches[0].canonical_source == "name_override"
    assert mismatches[0].results_location_id == "7"


def test_event_id_canonical_ignores_series_moves():
    from transform.geography.event_location_guard import (
        KNOWN_SERIES_MOVES,
        find_event_id_canonical_location_mismatches,
    )

    location_info = pd.DataFrame(
        [
            {"location_id": "13", "event_city": "Washington", "event_country": "United States"},
            {"location_id": "156", "event_city": "Lyon", "event_country": "France"},
        ]
    )
    catalog = pd.DataFrame(
        [
            {
                "event_id": "999",
                "canonical_name": "Westie's Angels",
                "typical_location": "Washington, DC",
                "upcoming_location": "Lyon, France",
            }
        ]
    )
    results = pd.DataFrame(
        [{"event_name": "Westie's Angels", "location_id": "13"}]
    )
    assert "Westie's Angels" in KNOWN_SERIES_MOVES
    assert "Global Grand Prix - West Coast Swing Reunion" in KNOWN_SERIES_MOVES
    assert "Countdown Swing Boston" in KNOWN_SERIES_MOVES
    mismatches = find_event_id_canonical_location_mismatches(
        results,
        location_info,
        catalog,
        known_metadata={},
        name_overrides={},
    )
    assert mismatches == []

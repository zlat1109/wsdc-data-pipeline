"""Tests for db/quality_checks definitions."""

from db.quality_checks import ALL_CHECKS, CORE_CHECKS, EXTENDED_CHECKS


def test_core_checks_are_subset_of_all():
    core_names = {c.name for c in CORE_CHECKS}
    all_names = {c.name for c in ALL_CHECKS}
    assert core_names.issubset(all_names)


def test_check_names_unique():
    names = [c.name for c in ALL_CHECKS]
    assert len(names) == len(set(names))


def test_core_checks_include_ci_invariants():
    names = {c.name for c in CORE_CHECKS}
    assert names >= {
        "results_null_location_id",
        "split_names_same_geo",
        "noncanonical_divisions",
        "points_history_drift",
        "roles_history_drift",
        "names_history_drift",
    }


def test_extended_checks_cover_known_regression_categories():
    names = {c.name for c in EXTENDED_CHECKS}
    assert "edition_calendar_orphan_event_ids" in names
    assert "events_list_current_empty" in names
    assert "schedule_orphan_location_id" in names
    assert "all_caps_cities" in names
    assert "phantom_ids_not_merged" in names
    assert "swing_snow_alias" in names
    assert "double_space_event_location" in names
    assert "dancers_empty_name" in names
    assert "non_us_event_state" in names


def test_singapore_city_state_allowed_in_city_equals_country():
    check = next(c for c in EXTENDED_CHECKS if c.name == "city_equals_country")
    assert "Singapore" in check.sql
    assert "trim(event_country) NOT IN" in check.sql


def test_non_us_event_state_uses_shared_us_country_list():
    check = next(c for c in EXTENDED_CHECKS if c.name == "non_us_event_state")
    for country in (
        "United States",
        "USA",
        "US",
        "U.S.",
        "U.S.A.",
    ):
        assert country in check.sql


def test_split_names_same_geo_does_not_exempt_keep_separate():
    """KEEP_SEPARATE pairs must keep distinct cities; gate must still catch same-geo."""
    from transform.geography.geo_event import KEEP_SEPARATE_EVENT_PAIRS

    check = next(c for c in CORE_CHECKS if c.name == "split_names_same_geo")
    assert "keep_separate" not in check.sql.lower()
    assert "EVENT_NAME_YEAR_LOCATION_OVERRIDES" in check.description
    # Documented pairs still exist for merge/classify (not for gate exemption).
    assert frozenset({191, 230}) in KEEP_SEPARATE_EVENT_PAIRS
    assert frozenset({306, 367}) in KEEP_SEPARATE_EVENT_PAIRS

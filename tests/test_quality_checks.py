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
    assert names == {
        "results_null_location_id",
        "split_names_same_geo",
        "noncanonical_divisions",
        "points_history_drift",
    }


def test_extended_checks_cover_known_regression_categories():
    names = {c.name for c in EXTENDED_CHECKS}
    assert "all_caps_cities" in names
    assert "phantom_ids_not_merged" in names
    assert "swing_snow_alias" in names
    assert "double_space_event_location" in names


def test_singapore_whitelisted_in_city_equals_country():
    check = next(c for c in EXTENDED_CHECKS if c.name == "city_equals_country")
    assert "159" in check.sql and "244" in check.sql

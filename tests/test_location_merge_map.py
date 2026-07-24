"""Tests for manual location_id merge map and corrections."""

from transform.knowledge.locations import (
    LOCATION_ID_CORRECTIONS,
    LOCATION_ID_MERGE_MAP,
)


def test_merge_map_targets_exist_as_canonical_or_survivor():
    canonical = set(LOCATION_ID_MERGE_MAP.values())
    sources = set(LOCATION_ID_MERGE_MAP.keys())
    assert sources.isdisjoint(canonical), "source id must not also be a canonical target"


def test_amsterdam_and_anaheim_merges_configured():
    assert LOCATION_ID_MERGE_MAP["373"] == "191"
    assert LOCATION_ID_MERGE_MAP["291"] == "23"
    assert LOCATION_ID_MERGE_MAP["334"] == "127"


def test_north_myrtle_beach_spelling_merge():
    assert LOCATION_ID_MERGE_MAP["111"] == "325"
    patch = LOCATION_ID_CORRECTIONS[325]
    assert patch["event_city"] == "North Myrtle Beach"
    assert patch.get("latitude") and patch.get("longitude")


def test_non_us_corrections_clear_event_state():
    for loc_id in (191, 107, 234, 226, 148, 105, 127):
        patch = LOCATION_ID_CORRECTIONS[loc_id]
        assert patch.get("event_state") == ""


def test_n_myrtle_beach_country_fixed():
    patch = LOCATION_ID_CORRECTIONS[325]
    assert patch["event_country"] == "United States"
    assert patch["event_state"] == "South Carolina"


def test_corrections_exclude_merge_map_sources():
    sources = set(LOCATION_ID_MERGE_MAP.keys())
    correction_ids = {str(loc_id) for loc_id in LOCATION_ID_CORRECTIONS}
    assert sources.isdisjoint(correction_ids), (
        "LOCATION_ID_CORRECTIONS must not patch merge-map source ids "
        "(rows are deleted by apply_merges)"
    )


def test_legacy_coordinate_duplicate_merges_configured():
    """New WSDC duplicate location_ids → canonical rows with coordinates."""
    assert LOCATION_ID_MERGE_MAP["302"] == "55"
    assert LOCATION_ID_MERGE_MAP["369"] == "208"
    assert LOCATION_ID_MERGE_MAP["385"] == "208"
    assert LOCATION_ID_MERGE_MAP["388"] == "7"
    assert LOCATION_ID_MERGE_MAP["436"] == "127"
    assert LOCATION_ID_MERGE_MAP["467"] == "213"
    assert LOCATION_ID_MERGE_MAP["470"] == "23"


def test_location_353_is_silver_spring_not_washington_md():
    """WSDC 'Washington, MD' for Dance Jam / Westie Weekend → Silver Spring."""
    assert "353" not in LOCATION_ID_MERGE_MAP
    patch = LOCATION_ID_CORRECTIONS[353]
    assert patch["event_city"] == "Silver Spring"
    assert patch["event_state"] == "Maryland"
    assert patch["event_country"] == "United States"
    assert patch["event_location"] == "Silver Spring, MD, United States"
    assert patch.get("latitude") and patch.get("longitude")
    assert patch.get("coordinates_valid") in {"t", "true", True}

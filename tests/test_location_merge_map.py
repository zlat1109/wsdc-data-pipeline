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

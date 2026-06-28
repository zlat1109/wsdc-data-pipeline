"""Tests for result → catalog event name mappings."""

from pathlib import Path

import pandas as pd

from transform.knowledge import (
    EVENT_NAME_NORMALIZATION,
    RESULT_TO_CATALOG_EVENT_NAME,
    build_event_name_normalization,
)


def test_result_to_catalog_targets_exist_in_events_wsdc():
    data_dir = Path(__file__).resolve().parents[1] / "data"
    catalog = set(
        pd.read_csv(data_dir / "events_wsdc.csv", dtype=str)["name"].dropna().str.strip()
    )
    missing = [
        (alias, canonical)
        for alias, canonical in RESULT_TO_CATALOG_EVENT_NAME.items()
        if canonical not in catalog
    ]
    assert not missing, f"Unknown catalog targets: {missing[:5]}"


def test_build_event_name_normalization_is_stable():
    assert build_event_name_normalization() == EVENT_NAME_NORMALIZATION


def test_orphan_result_names_normalize_to_catalog():
    """Top orphan names from staging audit should map to catalog."""
    for alias, canonical in [
        ("Phoenix 4th of July", "4TH of July Convention"),
        ("MADjam", "Mid-Atlantic Dance Jam"),
        ("D-Townswing", "D-Town Swing"),
        ("Monterey Swingfest", "Monterey SwingFest"),
        ("Swing Fling 2024", "Swing Fling"),
        ("Swing&Snow", "Swing & Snow"),
    ]:
        assert EVENT_NAME_NORMALIZATION[alias] == canonical


def test_merge_map_excludes_geo_split_pairs():
    from transform.knowledge.event_aliases import MERGE_EVENT_ID_MAP

    blocked = {75, 152, 191, 230, 83, 204}
    assert not blocked.intersection(MERGE_EVENT_ID_MAP.keys())
    assert not blocked.intersection(MERGE_EVENT_ID_MAP.values())

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


def test_recent_result_only_events_present_in_events_wsdc():
    """New 2026 events must appear in export.events_wsdc (via event_editions)."""
    data_dir = Path(__file__).resolve().parents[1] / "data"
    names = set(
        pd.read_csv(data_dir / "events_wsdc.csv", dtype=str)["name"].dropna().str.strip()
    )
    for required in ("SwingLab Berlin", "Milan Swing Vibes"):
        assert required in names, f"{required} missing from events_wsdc.csv"
    from transform.knowledge.events import KNOWN_EVENT_METADATA

    assert KNOWN_EVENT_METADATA[389]["name"] == "SwingLab Berlin"
    assert KNOWN_EVENT_METADATA[405]["name"] == "Milan Swing Vibes"


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
        ("5280 Swing Dance Championships", "5280 Westival"),
        ("LoneStar Invitational", "Lone Star Invitational"),
        ("French Connection WCS", "FRENCH CONNECTION WCS"),
    ]:
        assert EVENT_NAME_NORMALIZATION[alias] == canonical


def test_5280_alias_points_to_westival_not_championships():
    assert RESULT_TO_CATALOG_EVENT_NAME["5280 Swing Dance Championships"] == "5280 Westival"
    assert "5280 Westival" not in RESULT_TO_CATALOG_EVENT_NAME
    from transform.knowledge.event_aliases import MERGE_EVENT_ID_MAP

    assert MERGE_EVENT_ID_MAP[406] == 197


def test_merge_map_excludes_geo_split_pairs():
    from transform.knowledge.event_aliases import MERGE_EVENT_ID_MAP

    blocked = {75, 152, 191, 230, 83, 204}
    assert not blocked.intersection(MERGE_EVENT_ID_MAP.keys())
    assert not blocked.intersection(MERGE_EVENT_ID_MAP.values())

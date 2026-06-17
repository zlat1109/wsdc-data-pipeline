"""Tests for unified level normalization (core.levels compatible)."""

from transform.normalize import normalize_level


def test_normalize_level_all_star_variants():
    assert normalize_level("ALS") == "All-Star"
    assert normalize_level("All Star") == "All-Star"
    assert normalize_level("Allstar") == "All-Star"

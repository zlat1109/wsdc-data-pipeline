"""Tests for division normalization."""

from transform.normalize import normalize_division, normalize_level


def test_normalize_all_stars_plural():
    assert normalize_division("All-Stars") == "All-Star"


def test_normalize_champions_plural():
    assert normalize_division("Champions") == "Champion"


def test_normalize_masters_plural():
    assert normalize_level("Masters") == "Master"


def test_normalize_professional_unchanged():
    assert normalize_division("Professional") == "Professional"

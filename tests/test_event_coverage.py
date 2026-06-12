"""Tests for event coverage matching."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from parser.event_name_matcher import find_best_match


def test_jack_and_jill_maps_to_jj_orama():
    match, score = find_best_match(
        "Jack & Jill O'Rama",
        ["J&J O'Rama", "Orange Blossom Dance Festival"],
        threshold=0.75,
    )
    assert match == "J&J O'Rama"
    assert score == 1.0


def test_fuzzy_substring_match():
    match, score = find_best_match(
        "Orange Blossom Dance Festival",
        ["Orange Blossom Dance Festival 2026"],
        threshold=0.75,
    )
    assert match is not None
    assert score >= 0.75


def test_split_pending_skips_events_already_in_db():
    from unittest.mock import MagicMock

    from event_db import split_pending_events

    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchall.return_value = [
        ("J&J O'Rama",),
        ("Orange Blossom Dance Festival",),
    ]

    events = [
        {"name": "Jack & Jill O'Rama", "results_year": 2026, "results_month": 6},
        {"name": "Orange Blossom Dance Festival", "results_year": 2026, "results_month": 6},
        {"name": "Baltic Swing", "results_year": 2026, "results_month": 6},
    ]
    pending, already = split_pending_events(conn, events)
    assert "Baltic Swing" in pending
    assert "Jack & Jill O'Rama" in already
    assert "Orange Blossom Dance Festival" in already

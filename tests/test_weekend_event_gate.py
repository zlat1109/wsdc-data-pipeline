"""Tests for weekend snapshot gate (past vs future events)."""

import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from event_db import event_has_concluded, event_results_edition, split_pending_events


def test_event_results_edition_from_start_date():
    event = {"name": "Milan Swing Vibes", "start_date": "2026-06-18", "end_date": "2026-06-21"}
    assert event_results_edition(event) == (2026, 6)


def test_event_has_concluded_uses_end_date():
    event = {"name": "SWINGAPALOOZA", "start_date": "2026-06-19", "end_date": "2026-06-21"}
    assert not event_has_concluded(event, date(2026, 6, 21))
    assert event_has_concluded(event, date(2026, 6, 22))


def test_split_pending_on_event_weekend_excludes_ongoing():
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchall.return_value = []

    events = [
        {"name": "Milan Swing Vibes", "start_date": "2026-06-18", "end_date": "2026-06-21"},
    ]
    pending, already = split_pending_events(conn, events, today=date(2026, 6, 19))
    assert pending == []
    assert already == []


def test_split_pending_skips_future_weekend_events():
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchall.return_value = []

    events = [
        {
            "name": "Liberty Swing Dance Championships",
            "start_date": "2026-06-25",
            "end_date": "2026-06-28",
        },
        {
            "name": "Milan Swing Vibes",
            "start_date": "2026-06-18",
            "end_date": "2026-06-21",
        },
    ]
    pending, already = split_pending_events(conn, events, today=date(2026, 6, 22))
    assert pending == ["Milan Swing Vibes"]
    assert already == []


def test_split_pending_skips_events_already_in_db_with_start_date():
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchall.return_value = [
        ("D-Town Swing",),
        ("Swingapalooza",),
    ]

    events = [
        {"name": "D-Townswing", "start_date": "2026-06-19", "end_date": "2026-06-21"},
        {"name": "SWINGAPALOOZA", "start_date": "2026-06-19", "end_date": "2026-06-21"},
    ]
    pending, already = split_pending_events(conn, events, today=date(2026, 6, 22))
    assert pending == []
    assert set(already) == {"D-Townswing", "SWINGAPALOOZA"}


def test_future_only_snapshot_yields_no_pending():
    from weekend_events import WeekendSnapshot, resolve_pending_snapshot

    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchall.return_value = []

    snap = WeekendSnapshot(
        weekend_start=date(2026, 6, 22),
        weekend_end=date(2026, 7, 5),
        events=[
            {
                "name": "BaroqueSwing",
                "start_date": "2026-06-25",
                "end_date": "2026-06-28",
            },
            {
                "name": "Swing Fiction",
                "start_date": "2026-06-26",
                "end_date": "2026-06-28",
            },
        ],
        source_path=Path("weekend_2026-06-22_2026-07-05.json"),
        generated_at=None,
    )

    import weekend_events as we

    original = we.list_snapshots
    we.list_snapshots = lambda: [snap]
    try:
        best, pending, already = resolve_pending_snapshot(conn, today=date(2026, 6, 19))
    finally:
        we.list_snapshots = original

    assert best is None
    assert pending == []
    assert already == []

"""Tests for weekend snapshot gate (past vs future events)."""

import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from event_db import event_has_concluded, event_results_edition, events_within_gate_lookback, split_pending_events


def test_event_results_edition_from_start_date():
    event = {"name": "Milan Swing Vibes", "start_date": "2026-06-18", "end_date": "2026-06-21"}
    assert event_results_edition(event) == (2026, 6)


def test_event_has_concluded_uses_end_date():
    event = {"name": "SWINGAPALOOZA", "start_date": "2026-06-19", "end_date": "2026-06-21"}
    assert not event_has_concluded(event, date(2026, 6, 21))
    assert event_has_concluded(event, date(2026, 6, 22))


def test_event_has_concluded_on_weekday_last_day():
    """Jul 2-6 events ending Monday Jul 6 are in gate for Monday probe."""
    event = {"name": "Americano Dance Camp", "start_date": "2026-07-02", "end_date": "2026-07-06"}
    assert event_has_concluded(event, date(2026, 7, 6))
    assert not event_has_concluded(event, date(2026, 7, 5))


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


def test_split_pending_matches_neverland_long_snapshot_name():
    """Year-suffix normalization must not break EVENT_NAME_MAPPINGS on raw name."""
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchall.return_value = [
        ("Neverland Swing",),
    ]

    events = [
        {
            "name": "NeverlandSwing Dutch Swing Championships 2026",
            "start_date": "2026-06-25",
            "end_date": "2026-06-29",
            "results_year": 2026,
            "results_month": 6,
        },
    ]
    pending, already = split_pending_events(conn, events, today=date(2026, 7, 14))
    assert pending == []
    assert already == ["NeverlandSwing Dutch Swing Championships 2026"]


def test_events_within_gate_lookback_excludes_stale_concluded():
    events = [
        {"name": "Old", "start_date": "2026-01-01", "end_date": "2026-01-03"},
        {"name": "Recent", "start_date": "2026-07-03", "end_date": "2026-07-05"},
    ]
    result = events_within_gate_lookback(events, today=date(2026, 7, 6), lookback_days=21)
    assert [event["name"] for event in result] == ["Recent"]


def test_future_only_snapshot_yields_no_pending():
    from weekend_events import WeekendSnapshot, resolve_event_gate, resolve_pending_snapshot

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
        _gate_snap, _gate_pending, _gate_already, status = resolve_event_gate(
            conn, today=date(2026, 6, 19)
        )
    finally:
        we.list_snapshots = original

    assert best is None
    assert pending == []
    assert already == []
    assert status == "no_concluded_events"


def test_resolve_event_gate_all_loaded():
    from weekend_events import WeekendSnapshot, resolve_event_gate

    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchall.return_value = [
        ("Neverland Swing",),
    ]

    snap = WeekendSnapshot(
        weekend_start=date(2026, 6, 22),
        weekend_end=date(2026, 6, 29),
        events=[
            {
                "name": "Neverland Swing",
                "start_date": "2026-06-25",
                "end_date": "2026-06-29",
            },
        ],
        source_path=Path("weekend_2026-06-22_2026-06-29.json"),
        generated_at=None,
    )

    import weekend_events as we

    original = we.list_snapshots
    we.list_snapshots = lambda: [snap]
    try:
        gate_snap, pending, already, status = resolve_event_gate(conn, today=date(2026, 6, 30))
    finally:
        we.list_snapshots = original

    assert status == "all_loaded"
    assert pending == []
    assert already == ["Neverland Swing"]
    assert gate_snap is snap


def test_resolve_event_gate_prefers_pending_over_newer_all_loaded_snapshot():
    """Jul 6 case: narrow Jun 25-28 snapshot (all loaded) must not hide Jul 4-5 pending."""
    from datetime import datetime

    from weekend_events import WeekendSnapshot, resolve_event_gate

    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchall.return_value = []

    narrow = WeekendSnapshot(
        weekend_start=date(2026, 6, 25),
        weekend_end=date(2026, 6, 28),
        events=[
            {
                "name": "BaroqueSwing",
                "start_date": "2026-06-25",
                "end_date": "2026-06-28",
            },
        ],
        source_path=Path("weekend_2026-06-25_2026-06-28.json"),
        generated_at=datetime(2026, 7, 4, 5, 51, 4),
    )
    broad = WeekendSnapshot(
        weekend_start=date(2026, 6, 29),
        weekend_end=date(2026, 7, 12),
        events=[
            {
                "name": "Wild Wild Westie",
                "start_date": "2026-07-03",
                "end_date": "2026-07-05",
            },
        ],
        source_path=Path("weekend_2026-06-29_2026-07-12.json"),
        generated_at=datetime(2026, 7, 2, 15, 8, 38),
    )

    import weekend_events as we

    original = we.list_snapshots
    we.list_snapshots = lambda: [narrow, broad]
    try:
        gate_snap, pending, already, status = resolve_event_gate(conn, today=date(2026, 7, 6))
    finally:
        we.list_snapshots = original

    assert status == "pending"
    assert "Wild Wild Westie" in pending
    assert gate_snap is broad


def test_resolve_event_gate_merges_carry_over_from_older_snapshot():
    """Missed last-week event + new weekend events stay in one pending gate."""
    from datetime import datetime

    from weekend_events import WeekendSnapshot, resolve_event_gate

    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchall.return_value = []

    older = WeekendSnapshot(
        weekend_start=date(2026, 6, 22),
        weekend_end=date(2026, 7, 5),
        events=[
            {
                "name": "Neverland Swing",
                "start_date": "2026-06-25",
                "end_date": "2026-06-29",
            },
        ],
        source_path=Path("weekend_2026-06-22_2026-07-05.json"),
        generated_at=datetime(2026, 6, 30, 12, 0, 0),
    )
    current = WeekendSnapshot(
        weekend_start=date(2026, 6, 29),
        weekend_end=date(2026, 7, 12),
        events=[
            {
                "name": "Wild Wild Westie",
                "start_date": "2026-07-03",
                "end_date": "2026-07-05",
            },
            {
                "name": "Phoenix 4th of July",
                "start_date": "2026-07-03",
                "end_date": "2026-07-05",
            },
        ],
        source_path=Path("weekend_2026-06-29_2026-07-12.json"),
        generated_at=datetime(2026, 7, 2, 15, 8, 38),
    )

    import weekend_events as we

    original = we.list_snapshots
    we.list_snapshots = lambda: [older, current]
    try:
        gate_snap, pending, already, status = resolve_event_gate(conn, today=date(2026, 7, 6))
    finally:
        we.list_snapshots = original

    assert status == "pending"
    assert pending == ["Neverland Swing", "Wild Wild Westie", "Phoenix 4th of July"]
    assert already == []
    assert gate_snap is current

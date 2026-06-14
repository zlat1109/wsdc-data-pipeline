"""Tests for collapsing schedule editions to one row per event."""

import json
from pathlib import Path

from transform.events_list_current import build_events_list_current, schedule_event_key
from transform.events_list_mapping import CatalogEvent, build_url_index, map_scheduled_event


def _atlanta_catalog() -> list[CatalogEvent]:
    return [
        CatalogEvent(
            event_id=211,
            name="Atlanta Swing Classic",
            url="https://www.atlantaswingclassic.com/",
            url_norm="atlantaswingclassic.com",
            typical_location="Atlanta, GA, USA",
        )
    ]


def _load_current_events() -> list[dict]:
    raw = json.loads(
        (Path(__file__).resolve().parents[1] / "data/events_list/current.json").read_text()
    )
    return raw["events"]


def test_atlanta_swing_classic_collapses_to_nearest_edition():
    events = [e for e in _load_current_events() if e["event_name"] == "Atlanta Swing Classic"]
    assert len(events) == 3

    catalog = _atlanta_catalog()
    current = build_events_list_current(events, catalog)

    assert len(current) == 1
    assert current[0]["start_date"] == "2026-10-01"
    assert current[0]["upcoming_editions"] == 3
    assert current[0]["schedule_event_key"] == "evt:211"


def test_current_row_count_less_than_editions_with_synthetic_rows():
    catalog = _atlanta_catalog()
    events = [
        {
            "source_fingerprint": "fp2026",
            "event_name": "Atlanta Swing Classic",
            "start_date": "2026-10-01",
            "end_date": "2026-10-04",
            "url": "https://www.atlantaswingclassic.com/",
            "location_raw": "Atlanta, GA, United States",
            "status_event": "Registry Event",
            "is_active": True,
        },
        {
            "source_fingerprint": "fp2027",
            "event_name": "Atlanta Swing Classic",
            "start_date": "2027-10-07",
            "end_date": "2027-10-10",
            "url": "https://www.atlantaswingclassic.com/",
            "location_raw": "Atlanta, GA, United States",
            "status_event": "Registry Event",
            "is_active": True,
        },
    ]
    current = build_events_list_current(events, catalog)
    assert len(current) == 1
    assert current[0]["source_fingerprint"] == "fp2026"


def test_schedule_event_key_uses_event_id_when_mapped():
    catalog = _atlanta_catalog()
    url_index = build_url_index(catalog)
    row = {
        "source_fingerprint": "fp2026",
        "event_name": "Atlanta Swing Classic",
        "start_date": "2026-10-01",
        "url": "https://www.atlantaswingclassic.com/",
        "location_raw": "Atlanta, GA, United States",
        "status_event": "Registry Event",
    }
    mapping = map_scheduled_event(row, catalog, url_index, [c.name for c in catalog])
    assert schedule_event_key(row, mapping) == "evt:211"


def test_unmapped_event_uses_url_key():
    catalog: list[CatalogEvent] = []
    url_index = build_url_index(catalog)
    row = {
        "source_fingerprint": "abc123",
        "event_name": "Brand New Trial",
        "start_date": "2026-12-01",
        "url": "https://example.com/new-trial/",
        "location_raw": "Somewhere",
        "status_event": "Trial Event",
        "is_active": True,
    }
    mapping = map_scheduled_event(row, catalog, url_index, [])
    assert mapping.canonical_event_id is None
    assert schedule_event_key(row, mapping) == "url:example.com/new-trial"


def test_review_match_does_not_use_event_id_key():
    """Fuzzy review matches must not collapse unrelated rows via evt: key."""
    catalog = [
        CatalogEvent(
            event_id=999,
            name="Real Catalog Event",
            url="https://real.example.com/",
            url_norm="real.example.com",
            typical_location="City A",
        )
    ]
    url_index = build_url_index(catalog)
    rows = [
        {
            "source_fingerprint": "fp-a",
            "event_name": "Totally Different A",
            "start_date": "2026-11-01",
            "url": "https://a.example.com/",
            "location_raw": "City X",
            "status_event": "Registry Event",
            "is_active": True,
        },
        {
            "source_fingerprint": "fp-b",
            "event_name": "Totally Different B",
            "start_date": "2026-12-01",
            "url": "https://b.example.com/",
            "location_raw": "City Y",
            "status_event": "Registry Event",
            "is_active": True,
        },
    ]
    for row in rows:
        mapping = map_scheduled_event(row, catalog, url_index, [c.name for c in catalog])
        assert mapping.match_status != "confirmed"
        assert schedule_event_key(row, mapping).startswith("url:")

    current = build_events_list_current(rows, catalog)
    assert len(current) == 2

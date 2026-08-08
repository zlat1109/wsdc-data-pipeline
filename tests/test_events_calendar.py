"""Tests for WSDC Events Calendar scrape + normalize + durable upsert helpers."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "db"))

from edition_calendar import calendar_status_from_flags, rows_for_upsert
from parser.events_calendar_scraper import extract_calendar_events_json
from transform.events_calendar_match import match_calendar_to_editions
from transform.events_calendar_normalize import (
    inclusive_end_from_fullcalendar,
    normalize_calendar_event,
    normalize_calendar_events,
)

_SAMPLE_HTML = """
<html><script>
document.addEventListener('DOMContentLoaded', function() {
  var calendar = new FullCalendar.Calendar(el, {
"events":[{"title":"Atlanta Swing Classic","start":"2025-10-02","end":"2025-10-06","url":"https:\\/\\/atlantaswingclassic.com\\/"},{"title":"Municorn Swing (On Hiatus)","start":"2024-01-25","end":"2024-01-29","url":"https:\\/\\/municornswing.com"},{"title":"MY Swing","start":"2026-07-09","end":"2026-07-13","url":"https:\\/\\/example.com\\/myswing"}]});
  calendar.render();
});
</script></html>
"""


def test_extract_calendar_events_json():
    events = extract_calendar_events_json(_SAMPLE_HTML)
    assert len(events) == 3
    assert events[0]["title"] == "Atlanta Swing Classic"


def test_inclusive_end_exclusive_fullcalendar():
    start = date(2026, 7, 9)
    end_exclusive = date(2026, 7, 13)
    assert inclusive_end_from_fullcalendar(start, end_exclusive) == date(2026, 7, 12)


def test_normalize_drops_hiatus_flag_and_min_start():
    raw = extract_calendar_events_json(_SAMPLE_HTML)
    rows = normalize_calendar_events(raw, min_start=date(2025, 1, 1))
    assert len(rows) == 2
    atlanta = next(r for r in rows if r["event_name"] == "Atlanta Swing Classic")
    assert atlanta["start_date"] == "2025-10-02"
    assert atlanta["end_date"] == "2025-10-05"
    my_swing = next(r for r in rows if r["event_name"] == "MY Swing")
    assert my_swing["end_date"] == "2026-07-12"


def test_normalize_keeps_cross_year_overlap_on_min_start():
    raw = [
        {
            "title": "Countdown Swing Boston",
            "start": "2024-12-31",
            "end": "2025-01-06",
            "url": "http://countdownswingboston.com",
        }
    ]
    rows = normalize_calendar_events(raw, min_start=date(2025, 1, 1))
    assert len(rows) == 1
    assert rows[0]["event_name"] == "Countdown Swing Boston"
    assert rows[0]["results_year"] == 2025
    assert rows[0]["results_month"] == 1


def test_normalize_hiatus_flag():
    row = normalize_calendar_event(
        {
            "title": "Municorn Swing (On Hiatus)",
            "start": "2024-01-25",
            "end": "2024-01-29",
            "url": "https://municornswing.com",
        }
    )
    assert row is not None
    assert "hiatus" in row["flags"]
    assert row["event_name"] == "Municorn Swing"
    assert calendar_status_from_flags(row["flags"]) == "hiatus"


def test_normalize_nye_start_only_uses_next_january_results_year():
    row = normalize_calendar_event(
        {
            "title": "SwingVester",
            "start": "2026-12-30",
            "end": "2026-12-30",  # exclusive end == start → invalid_end
            "url": "https://www.swingvester.com/",
        }
    )
    assert row is not None
    assert "invalid_end" in row["flags"]
    assert row["end_date"] == ""
    assert row["results_year"] == 2027
    assert row["results_month"] == 1
    assert row["edition_ym_candidates"][0] == "2027-01"


def test_match_by_name_and_ym():
    cal = normalize_calendar_events(
        [{"title": "Atlanta Swing Classic", "start": "2025-10-02", "end": "2025-10-06", "url": ""}],
        min_start=None,
    )
    editions = pd.DataFrame(
        [
            {
                "edition_id": "e1",
                "event_id": "42",
                "event_name": "Atlanta Swing Classic",
                "event_year": "2025",
                "event_month": "10",
            }
        ]
    )
    catalog = pd.DataFrame(
        [{"event_id": "42", "canonical_name": "Atlanta Swing Classic", "url": ""}]
    )
    rows, summary = match_calendar_to_editions(cal, editions, catalog)
    assert summary["matched"] == 1
    assert rows[0]["matched_event_id"] == "42"
    assert rows[0]["matched_edition_id"] == "e1"
    assert rows[0]["matched_event_year"] == "2025"
    assert rows[0]["matched_event_month"] == "10"


def test_match_prefers_event_id_that_still_has_editions():
    """Stale catalog duplicate must not win over the live series id."""
    cal = normalize_calendar_events(
        [{"title": "SwingLab Berlin", "start": "2026-07-10", "end": "2026-07-13", "url": ""}],
        min_start=None,
    )
    editions = pd.DataFrame(
        [
            {
                "edition_id": "7905",
                "event_id": "396",
                "event_name": "SwingLab Berlin",
                "event_year": "2026",
                "event_month": "7",
            }
        ]
    )
    catalog = pd.DataFrame(
        [
            {"event_id": "389", "canonical_name": "SwingLab Berlin", "url": ""},
            {"event_id": "396", "canonical_name": "SwingLab Berlin", "url": ""},
        ]
    )
    rows, summary = match_calendar_to_editions(cal, editions, catalog)
    assert summary["matched"] == 1
    assert rows[0]["matched_event_id"] == "396"
    assert rows[0]["matched_edition_id"] == "7905"


def test_rows_for_upsert_keeps_hiatus_planned_dates():
    rows = rows_for_upsert(
        [
            {
                "matched_event_id": "92",
                "matched_event_year": "2025",
                "matched_event_month": "3",
                "match_status": "matched",
                "start_date": "2025-02-27",
                "end_date": "2025-03-03",
                "flags": ["hiatus"],
                "date_source": "wsdc_calendar",
                "source_fingerprint": "abc",
                "calendar_title": "Madjam (On Hiatus)",
                "url": "http://example.com",
                "match_via": "name",
                "results_year": 2025,
                "results_month": 3,
            }
        ]
    )
    assert len(rows) == 1
    assert rows[0]["calendar_status"] == "hiatus"
    assert rows[0]["planned_start_date"] == "2025-02-27"
    assert rows[0]["event_year"] == 2025
    assert rows[0]["event_month"] == 3


def test_ensure_skips_scrape_when_durable_present(monkeypatch):
    calls = {"enrich": 0, "scrape": 0}

    class _Cur:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params=None):
            self._sql = sql

        def fetchone(self):
            return (12,)

    class _Conn:
        def cursor(self):
            return _Cur()

    def fake_enrich(conn):
        calls["enrich"] += 1
        return (1, 0)

    def fake_scrape():
        calls["scrape"] += 1
        raise AssertionError("scrape should not run")

    monkeypatch.setattr("edition_calendar.enrich_event_editions_dates", fake_enrich)
    monkeypatch.setattr(
        "edition_calendar.durable_date_count", lambda conn: 12
    )
    monkeypatch.setattr(
        "parser.events_calendar_scraper.scrape_events_calendar", fake_scrape
    )

    from edition_calendar import ensure_edition_calendar_after_load

    report = ensure_edition_calendar_after_load(_Conn())
    assert report["action"] == "enrich_only"
    assert calls["enrich"] == 1
    assert calls["scrape"] == 0

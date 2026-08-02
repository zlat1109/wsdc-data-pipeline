"""Smoke test: build year calendar from real pipeline data dir."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from transform.year_event_calendar.build import build_year_event_calendar, spike_expected_accuracy

DATA = Path(__file__).resolve().parents[1] / "data"


def test_build_year_event_calendar_smoke():
    if not (DATA / "event_editions.csv").exists():
        return
    payload = build_year_event_calendar(DATA, as_of=date(2026, 8, 2), year_radius=2)
    assert payload["years"] == [2024, 2025, 2026, 2027, 2028]
    assert payload["default_year"] == 2026
    assert len(payload["events"]) > 0
    assert "en" in payload["disclaimer"]
    statuses = {e["status"] for e in payload["events"]}
    assert "confirmed" in statuses
    # Day-precision coverage starts ~2025 in current exports
    assert payload["counts_by_year"]["2025"] > 0
    assert payload["counts_by_year"]["2026"] > 0


def test_spike_2025_to_2026_has_reasonable_match_rate():
    if not (DATA / "event_editions.csv").exists():
        return
    report = spike_expected_accuracy(DATA, prior_year=2025, target_year=2026)
    assert report["prior_confirmed"] > 50
    assert report["match_rate"] is not None
    assert report["match_rate"] >= 0.5

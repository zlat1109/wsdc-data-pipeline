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
    assert 2024 not in payload["years"]  # no day-precision data
    assert 2025 in payload["years"]
    assert 2026 in payload["years"]
    assert payload["default_year"] == 2026
    assert len(payload["events"]) > 0
    assert "en" in payload["disclaimer"]
    statuses = {e["status"] for e in payload["events"]}
    assert "confirmed" in statuses
    assert payload["counts_by_year"]["2025"] > 0
    assert payload["counts_by_year"]["2026"] > 0
    # Expected horizon: current year only by default
    expected_by_year = {}
    for e in payload["events"]:
        if e["status"] != "expected":
            continue
        expected_by_year[e["year"]] = expected_by_year.get(e["year"], 0) + 1
    assert expected_by_year.get(2027, 0) == 0
    assert expected_by_year.get(2028, 0) == 0
    assert all(
        (e.get("name") or "").lower() not in {"nan", "none", ""}
        for e in payload["events"]
    )


def test_spike_2025_to_2026_has_reasonable_match_rate():
    if not (DATA / "event_editions.csv").exists():
        return
    report = spike_expected_accuracy(DATA, prior_year=2025, target_year=2026)
    assert report["prior_confirmed"] > 50
    assert report["match_rate"] is not None
    assert report["match_rate"] >= 0.5

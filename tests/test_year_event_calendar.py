"""Tests for year event calendar weekends + expected YoY matching."""

from __future__ import annotations

from datetime import date

from transform.year_event_calendar.expected import (
    iter_expected_candidates,
    match_expected_to_confirmed,
    project_start_to_year,
    within_expected_window,
)
from transform.year_event_calendar.weekends import weekend_bounds, weekend_key
from transform.year_event_calendar.build import _clean_name


def test_clean_name_rejects_nan_strings():
    assert _clean_name(None) is None
    assert _clean_name("nan") is None
    assert _clean_name("NaN") is None
    assert _clean_name("  Berlin Swing  ") == "Berlin Swing"


def test_weekend_bounds_thursday_start():
    thu, sun = weekend_bounds(date(2026, 7, 30))  # Thursday
    assert thu == date(2026, 7, 30)
    assert sun == date(2026, 8, 2)


def test_weekend_bounds_saturday_and_monday():
    thu, sun = weekend_bounds(date(2026, 8, 1))  # Saturday
    assert thu == date(2026, 7, 30)
    assert sun == date(2026, 8, 2)
    thu2, sun2 = weekend_bounds(date(2026, 8, 3))  # Monday → prior weekend
    assert thu2 == date(2026, 7, 30)
    assert sun2 == date(2026, 8, 2)


def test_weekend_key_stable():
    assert weekend_key(date(2026, 7, 31)) == "2026-07-30"


def test_project_leap_day():
    assert project_start_to_year(date(2024, 2, 29), 2025) == date(2025, 2, 28)
    assert project_start_to_year(date(2024, 3, 15), 2025) == date(2025, 3, 15)


def test_within_expected_window_wsdc_one_week():
    assert within_expected_window(date(2026, 6, 10), date(2026, 6, 17))
    assert not within_expected_window(date(2026, 6, 10), date(2026, 6, 18))


def test_match_expected_to_confirmed():
    confirmed = {42: [date(2026, 6, 12)]}
    assert match_expected_to_confirmed(
        event_id=42,
        projected_start=date(2026, 6, 10),
        confirmed_by_event=confirmed,
    ) == date(2026, 6, 12)
    assert (
        match_expected_to_confirmed(
            event_id=42,
            projected_start=date(2026, 6, 1),
            confirmed_by_event=confirmed,
        )
        is None
    )


def test_iter_expected_skips_known_ids():
    priors = [
        {
            "event_id": 1,
            "name": "A",
            "start_date": date(2025, 5, 8),
            "end_date": date(2025, 5, 11),
            "status": "confirmed",
            "kind": "registry",
        },
        {
            "event_id": 2,
            "name": "B",
            "start_date": date(2025, 5, 15),
            "end_date": None,
            "status": "confirmed",
            "kind": "trial",
        },
    ]
    stubs = iter_expected_candidates(priors, target_year=2026, skip_event_ids={1})
    assert len(stubs) == 1
    assert stubs[0]["event_id"] == 2
    assert stubs[0]["start_date"] == date(2026, 5, 15)
    assert stubs[0]["status"] == "expected"

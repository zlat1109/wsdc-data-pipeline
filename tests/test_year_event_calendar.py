"""Tests for year event calendar weekends + expected YoY matching."""

from __future__ import annotations

from datetime import date

import pandas as pd

from transform.year_event_calendar.expected import (
    iter_expected_candidates,
    match_expected_to_confirmed,
    project_start_to_year,
    within_expected_window,
)
from transform.year_event_calendar.weekends import weekend_bounds, weekend_key
from transform.year_event_calendar.build import (
    _clean_name,
    _enrich_geo,
    _location_id_by_event,
)


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


def test_enrich_geo_inherits_location_id_from_editions_map():
    locations = pd.DataFrame(
        [
            {
                "location_id": 29,
                "event_city": "Denver",
                "event_country": "United States",
                "latitude": 39.7392,
                "longitude": -104.9903,
                "coordinates_valid": True,
            }
        ]
    )
    catalog = pd.DataFrame(
        [
            {
                "event_id": 197,
                "canonical_name": "5280 Westival",
                "url": None,
                "typical_city": "Denver",
                "typical_country": "United States",
            }
        ]
    )
    rows = [
        {
            "event_id": 197,
            "name": "5280 Westival",
            "city": None,
            "country": None,
            "location_id": None,
            "url": None,
        }
    ]
    _enrich_geo(rows, locations, catalog, location_id_by_event={197: 29})
    assert rows[0]["location_id"] == 29
    assert rows[0]["lat"] == 39.7392
    assert rows[0]["lon"] == -104.9903
    assert rows[0]["city"] == "Denver"


def test_enrich_geo_city_country_fallback():
    locations = pd.DataFrame(
        [
            {
                "location_id": 1,
                "event_city": "Venray",
                "event_country": "Netherlands",
                "latitude": 51.525,
                "longitude": 5.975,
                "coordinates_valid": True,
            }
        ]
    )
    catalog = pd.DataFrame(columns=["event_id", "canonical_name", "url"])
    rows = [
        {
            "event_id": None,
            "name": "Dutch Open Wcs",
            "city": "Venray",
            "country": "Netherlands",
            "location_id": None,
            "url": None,
        }
    ]
    _enrich_geo(rows, locations, catalog, location_id_by_event={})
    assert rows[0]["lat"] == 51.525
    assert rows[0]["lon"] == 5.975


def test_location_id_by_event_picks_latest(tmp_path):
    path = tmp_path / "event_editions.csv"
    path.write_text(
        "event_id,location_id,start_date\n"
        "197,10,2024-03-01\n"
        "197,29,2025-03-20\n"
        "197,29,\n",
        encoding="utf-8",
    )
    assert _location_id_by_event(tmp_path)[197] == 29


def test_latest_confirmed_priors_and_terminal_block():
    from transform.year_event_calendar.build import (
        _ids_blocked_by_terminal,
        _latest_confirmed_priors,
    )

    rows = [
        {
            "event_id": 1,
            "start_date": date(2024, 5, 10),
            "status": "confirmed",
            "name": "A",
        },
        {
            "event_id": 1,
            "start_date": date(2025, 5, 12),
            "status": "confirmed",
            "name": "A",
        },
        {
            "event_id": 2,
            "start_date": date(2025, 6, 1),
            "status": "hiatus",
            "name": "B",
        },
        {
            "event_id": 2,
            "start_date": date(2024, 6, 1),
            "status": "confirmed",
            "name": "B",
        },
    ]
    priors = _latest_confirmed_priors(
        [r for r in rows if r["status"] == "confirmed"],
        before_year=2026,
    )
    by_id = {r["event_id"]: r["start_date"] for r in priors}
    assert by_id[1] == date(2025, 5, 12)
    assert by_id[2] == date(2024, 6, 1)  # latest confirmed still 2024
    blocked = _ids_blocked_by_terminal(rows, before_year=2026)
    assert 2 in blocked
    assert 1 not in blocked
    # Production skips blocked ids before emitting expected
    emit_ids = {eid for eid in by_id if eid not in blocked}
    assert emit_ids == {1}


def test_fill_missing_end_dates_uses_prior_duration_then_weekend():
    from transform.year_event_calendar.build import _fill_missing_end_dates

    rows = [
        {
            "event_id": 142,
            "name": "The Chicago Classic",
            "start_date": date(2025, 3, 13),
            "end_date": date(2025, 3, 16),
            "status": "confirmed",
        },
        {
            "event_id": 142,
            "name": "The Chicago Classic",
            "start_date": date(2026, 3, 19),
            "end_date": None,
            "status": "confirmed",
        },
        {
            "event_id": 999,
            "name": "Lonely Start",
            "start_date": date(2026, 4, 9),  # Thursday
            "end_date": None,
            "status": "confirmed",
        },
    ]
    _fill_missing_end_dates(rows)
    assert rows[1]["end_date"] == date(2026, 3, 22)  # +3 days from 2025 span
    assert rows[2]["end_date"] == date(2026, 4, 12)  # weekend Sunday


def test_fingerprint_and_weekend_dedupe_collapses_title_variants():
    from transform.year_event_calendar.build import (
        _dedupe_weekend_name_collisions,
        _fingerprint_event_name,
        _resolve_merge_event_id,
    )

    assert _fingerprint_event_name("The Boston Tea Party") == _fingerprint_event_name(
        "Boston Tea Party"
    )
    assert _fingerprint_event_name("Paris Swing Classic") == "paris westie"
    assert _resolve_merge_event_id(307) == 272
    assert _resolve_merge_event_id(543) == 272
    assert _resolve_merge_event_id(566) == 9

    rows = [
        {
            "event_id": 543,
            "name": "Paris Swing Classic",
            "start_date": date(2027, 2, 25),
            "end_date": date(2027, 3, 1),
            "status": "confirmed",
            "source": "edition_calendar_dates",
        },
        {
            "event_id": 272,
            "name": "Paris Swing Classic",
            "start_date": date(2027, 2, 25),
            "end_date": date(2027, 3, 1),
            "status": "confirmed",
            "source": "scheduled_events",
        },
        {
            "event_id": 9,
            "name": "Boston Tea Party",
            "start_date": date(2027, 3, 19),
            "end_date": date(2027, 3, 22),
            "status": "confirmed",
            "source": "edition_calendar_dates",
        },
        {
            "event_id": 566,
            "name": "The Boston Tea Party",
            "start_date": date(2027, 3, 19),
            "end_date": date(2027, 3, 22),
            "status": "confirmed",
            "source": "scheduled_events",
        },
    ]
    # Simulate post-merge ids
    for r in rows:
        r["event_id"] = _resolve_merge_event_id(r["event_id"])
    out = _dedupe_weekend_name_collisions(rows)
    assert len(out) == 2
    by_fp = {_fingerprint_event_name(r["name"]): r for r in out}
    assert by_fp["paris westie"]["event_id"] == 272
    assert by_fp["boston tea"]["source"] == "scheduled_events"


def test_calendar_continent_folds_south_america():
    from transform.year_event_calendar.build import _calendar_continent

    assert _calendar_continent("United States") == "America"
    assert _calendar_continent("Brazil") == "America"
    assert _calendar_continent("Germany") == "Europe"
    assert _calendar_continent("Japan") == "Asia"
    assert _calendar_continent("Australia") == "Australia"
    assert _calendar_continent(None) is None

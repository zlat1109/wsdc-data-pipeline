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


def test_iter_expected_forces_registry_kind():
    priors = [
        {
            "event_id": 1,
            "name": "A Trial Event",
            "start_date": date(2025, 5, 8),
            "end_date": date(2025, 5, 11),
            "status": "confirmed",
            "kind": "trial",
            "kind_from_schedule": True,
        },
    ]
    stubs = iter_expected_candidates(priors, target_year=2026, skip_event_ids=set())
    assert len(stubs) == 1
    assert stubs[0]["kind"] == "registry"
    assert "kind_from_schedule" not in stubs[0]


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


def test_rows_from_editions_keeps_result_backed_month_only_as_stats_only(tmp_path):
    from transform.year_event_calendar.build import _rows_from_editions

    path = tmp_path / "event_editions.csv"
    path.write_text(
        "event_id,event_name,event_year,event_month,edition_date,start_date,end_date,"
        "date_source,calendar_status,event_occurred,location_id,place_city,place_country,"
        "result_rows,unique_dancers,url,registry_status\n"
        "10,Month Stub Event,2025,7,2025-07-01,,,,,t,1,Paris,France,22,20,https://x.test,\n",
        encoding="utf-8",
    )

    rows = _rows_from_editions(tmp_path, stats_only_year=2025)
    assert len(rows) == 1
    assert rows[0]["start_date"] == date(2025, 7, 1)
    assert rows[0]["source"] == "event_editions_month_only"
    assert rows[0]["stats_only"] is True


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


def test_match_expected_cross_year_boundary():
    from transform.year_event_calendar.expected import match_expected_to_confirmed

    # SwingCouver NYE projection suppressed by SwingCo one week later in Jan
    hit = match_expected_to_confirmed(
        event_id=196,
        projected_start=date(2026, 12, 31),
        confirmed_by_event={196: [date(2027, 1, 7)]},
    )
    assert hit == date(2027, 1, 7)
    assert (
        match_expected_to_confirmed(
            event_id=196,
            projected_start=date(2026, 12, 31),
            confirmed_by_event={196: [date(2027, 1, 15)]},
        )
        is None
    )


def test_calendar_listing_mismatch_rejects_soul_flow_on_ggp():
    from transform.year_event_calendar.build import _calendar_listing_matches_event

    assert _calendar_listing_matches_event(
        "Global Grand Prix - West Coast Swing Reunion",
        "Global Grand Prix -- West Coast Swing Championships",
    )
    assert not _calendar_listing_matches_event(
        "Global Grand Prix - West Coast Swing Reunion",
        "Soul Flow - West Coast Swing Festival (Hiatus -- 2026)",
    )


def test_is_stale_expected_past_year_and_grace():
    from transform.year_event_calendar.expected import is_stale_expected

    as_of = date(2026, 8, 3)
    assert is_stale_expected(start=date(2025, 6, 1), end=date(2025, 6, 4), as_of=as_of)
    assert is_stale_expected(start=date(2026, 5, 30), end=date(2026, 6, 1), as_of=as_of)
    assert not is_stale_expected(start=date(2026, 7, 24), end=date(2026, 7, 27), as_of=as_of)
    assert not is_stale_expected(start=date(2026, 9, 18), end=date(2026, 9, 21), as_of=as_of)
    # Still inside grace (end + 7 days >= as_of)
    assert not is_stale_expected(
        start=date(2026, 7, 24), end=date(2026, 7, 27), as_of=date(2026, 8, 3)
    )
    assert is_stale_expected(
        start=date(2026, 7, 24), end=date(2026, 7, 27), as_of=date(2026, 8, 4)
    )


def test_drop_stale_expected_keeps_official_and_future():
    from transform.year_event_calendar.build import _drop_stale_expected

    as_of = date(2026, 8, 3)
    rows = [
        {
            "event_id": 1,
            "name": "Past Expected",
            "start_date": date(2026, 5, 1),
            "end_date": date(2026, 5, 4),
            "status": "expected",
            "source": "expected_yoy",
        },
        {
            "event_id": 2,
            "name": "Future Expected",
            "start_date": date(2026, 9, 10),
            "end_date": date(2026, 9, 13),
            "status": "expected",
            "source": "expected_yoy",
        },
        {
            "event_id": 3,
            "name": "Confirmed Past",
            "start_date": date(2026, 5, 1),
            "end_date": date(2026, 5, 4),
            "status": "confirmed",
            "source": "scheduled_events",
        },
        {
            "event_id": 4,
            "name": "Hiatus Past",
            "start_date": date(2026, 6, 1),
            "end_date": date(2026, 6, 3),
            "status": "hiatus",
            "source": "scheduled_events",
        },
    ]
    out = _drop_stale_expected(rows, as_of)
    ids = {r["event_id"] for r in out}
    assert ids == {2, 3, 4}


def test_dedupe_keeps_distinct_weekends_same_event_year():
    from transform.year_event_calendar.build import _dedupe_rows

    rows = [
        {
            "event_id": 342,
            "name": "Global Grand Prix -- West Coast Swing Championships",
            "start_date": date(2026, 9, 18),
            "end_date": date(2026, 9, 21),
            "status": "confirmed",
            "kind": "trial",
            "kind_from_schedule": True,
            "source": "scheduled_events",
        },
        {
            "event_id": 342,
            "name": "Global Grand Prix - West Coast Swing Reunion",
            "start_date": date(2026, 12, 11),
            "end_date": date(2026, 12, 13),
            "status": "hiatus",
            "kind": "registry",
            "source": "edition_calendar_dates",
        },
    ]
    out = _dedupe_rows(rows)
    assert len(out) == 2
    by_month = {r["start_date"].month: r for r in out}
    assert by_month[9]["kind"] == "trial"
    assert by_month[9].get("kind_from_schedule") is True
    assert by_month[12]["status"] == "hiatus"


def test_calendar_continent_folds_south_america():
    from transform.year_event_calendar.build import _calendar_continent

    assert _calendar_continent("United States") == "America"
    assert _calendar_continent("Brazil") == "America"
    assert _calendar_continent("Germany") == "Europe"
    assert _calendar_continent("Japan") == "Asia"
    assert _calendar_continent("Australia") == "Australia"
    assert _calendar_continent(None) is None


def test_prefer_row_does_not_steal_schedule_trial_lock():
    from transform.year_event_calendar.build import _prefer_row

    hiatus = {
        "event_id": 342,
        "start_date": date(2026, 12, 11),
        "status": "hiatus",
        "kind": "registry",
        "source": "edition_calendar_dates",
        "name": "Global Grand Prix",
    }
    schedule_trial = {
        "event_id": 342,
        "start_date": date(2026, 9, 18),
        "status": "confirmed",
        "kind": "trial",
        "kind_from_schedule": True,
        "source": "scheduled_events",
        "name": "Global Grand Prix",
        "url": "https://example.com",
    }
    winner = _prefer_row(hiatus, schedule_trial)
    assert winner["status"] == "hiatus"
    assert winner.get("kind_from_schedule") is not True
    assert winner.get("url") == "https://example.com"


def test_apply_kind_rules_first_year_trial_then_registry():
    from transform.year_event_calendar.build import _apply_kind_rules

    catalog = pd.DataFrame(
        [
            {
                "event_id": 381,
                "canonical_name": "Australian Classic",
                "registry_status": None,
                "first_edition_year": 2025,
            },
            {
                "event_id": 342,
                "canonical_name": "Global Grand Prix",
                "registry_status": "Trial Event",
                "first_edition_year": 2025,
            },
        ]
    )
    rows = [
        {
            "event_id": 381,
            "name": "The Australian Classic (Trial Event)",
            "start_date": date(2025, 1, 17),
            "status": "confirmed",
            "kind": "registry",
            "source": "edition_calendar_dates",
        },
        {
            "event_id": 381,
            "name": "The Australian Classic (Trial Event)",
            "start_date": date(2026, 1, 16),
            "status": "confirmed",
            "kind": "trial",
            "source": "edition_calendar_dates",
        },
        {
            "event_id": 342,
            "name": "Global Grand Prix - West Coast Swing Reunion",
            "start_date": date(2025, 6, 1),
            "status": "confirmed",
            "kind": "registry",
            "source": "edition_calendar_dates",
        },
        {
            "event_id": 381,
            "name": "The Australian Classic (Trial Event)",
            "start_date": date(2027, 1, 16),
            "status": "expected",
            "kind": "trial",
            "source": "expected_yoy",
        },
        {
            "event_id": 99,
            "name": "Brand New Swing",
            "start_date": date(2025, 5, 1),
            "status": "confirmed",
            "kind": "registry",
            "source": "edition_calendar_dates",
        },
        {
            "event_id": 50,
            "name": "Live Trial From Schedule",
            "start_date": date(2026, 8, 1),
            "status": "confirmed",
            "kind": "trial",
            "kind_from_schedule": True,
            "source": "scheduled_events",
        },
    ]
    first = {381: 2025, 342: 2025, 99: 2025}
    _apply_kind_rules(rows, first_points_year=first, catalog=catalog)
    assert rows[0]["kind"] == "trial"  # first year + name
    assert rows[1]["kind"] == "registry"  # second year despite Trial in title
    assert rows[2]["kind"] == "trial"  # first year heuristic / catalog
    assert rows[3]["kind"] == "registry"  # expected never trial
    assert rows[4]["kind"] == "trial"  # 2025 first points heuristic
    assert rows[5]["kind"] == "trial"  # locked from schedule

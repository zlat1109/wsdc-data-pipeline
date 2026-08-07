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
    # 2024-02-29 Thu → anniversary 2025-02-28 Fri → snap back to Thu
    assert project_start_to_year(date(2024, 2, 29), 2025) == date(2025, 2, 27)
    # 2024-03-15 Fri → anniversary 2025-03-15 Sat → snap to Fri
    assert project_start_to_year(date(2024, 3, 15), 2025) == date(2025, 3, 14)


def test_project_preserves_weekday_for_multi_year_horizon():
    """Naive month/day copy drifts; snap keeps Thu/Fri starts for expected YoY."""
    thu = date(2026, 5, 14)  # Thursday
    assert thu.weekday() == 3
    for year in (2027, 2028):
        projected = project_start_to_year(thu, year)
        assert projected.weekday() == 3
        assert abs((projected - thu.replace(year=year)).days) <= 3


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
    # 2025-05-08 Thu → 2026 snap keeps Thursday; span 3 days → Sun end
    assert stubs[0]["start_date"] == date(2026, 5, 7)
    assert stubs[0]["start_date"].weekday() == 3
    assert stubs[0]["end_date"] == date(2026, 5, 10)
    assert stubs[0]["end_date"].weekday() == 6


def test_iter_unlinked_trial_expected_keeps_trial_kind():
    from transform.year_event_calendar.expected import (
        iter_unlinked_trial_expected_candidates,
        unlinked_trial_series_key,
    )

    priors = [
        {
            "event_id": None,
            "name": "Swing Creation Hamburg",
            "country": "Germany",
            "city": "Hamburg",
            "start_date": date(2026, 8, 20),
            "end_date": date(2026, 8, 23),
            "status": "confirmed",
            "kind": "trial",
            "kind_from_schedule": True,
        },
        {
            # Already has a catalog id — ignored by the unlinked iterator.
            "event_id": 389,
            "name": "SwingLab Berlin",
            "country": "Germany",
            "start_date": date(2026, 7, 10),
            "end_date": date(2026, 7, 12),
            "status": "confirmed",
            "kind": "trial",
        },
    ]
    key = unlinked_trial_series_key(name="Swing Creation Hamburg", country="Germany")
    stubs = iter_unlinked_trial_expected_candidates(
        priors, target_year=2027, skip_keys=set()
    )
    assert len(stubs) == 1
    assert stubs[0]["name"] == "Swing Creation Hamburg"
    assert stubs[0]["event_id"] is None
    assert stubs[0]["kind"] == "trial"
    assert stubs[0]["provisional_unlinked_trial"] is True
    assert stubs[0]["status"] == "expected"
    assert stubs[0]["unlinked_trial_key"] == key
    assert stubs[0]["start_date"].year == 2027

    skipped = iter_unlinked_trial_expected_candidates(
        priors, target_year=2027, skip_keys={key}
    )
    assert skipped == []


def test_apply_kind_rules_keeps_provisional_unlinked_trial():
    from transform.year_event_calendar.build import _apply_kind_rules

    rows = [
        {
            "event_id": None,
            "name": "RiverSwingNights",
            "start_date": date(2027, 10, 1),
            "status": "expected",
            "source": "expected_yoy",
            "kind": "registry",
            "provisional_unlinked_trial": True,
        },
        {
            "event_id": 389,
            "name": "SwingLab Berlin",
            "start_date": date(2027, 7, 9),
            "status": "expected",
            "source": "expected_yoy",
            "kind": "trial",
        },
    ]
    _apply_kind_rules(rows, first_points_year={}, catalog=pd.DataFrame())
    assert rows[0]["kind"] == "trial"
    assert rows[1]["kind"] == "registry"


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


def test_year_override_beats_cross_year_start_for_prior_logic():
    from transform.year_event_calendar.build import _latest_confirmed_priors

    rows = [
        {
            "event_id": 42,
            "start_date": date(2024, 12, 31),
            "year": 2025,  # Cross-year Jan edition assigned to 2025
            "status": "confirmed",
            "name": "Countdown Swing Boston",
        }
    ]
    priors_2025 = _latest_confirmed_priors(rows, before_year=2025)
    priors_2026 = _latest_confirmed_priors(rows, before_year=2026)
    assert priors_2025 == []
    assert len(priors_2026) == 1


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


def test_fingerprint_fallback_collapses_stopword_only_titles():
    """Titles made only of stopwords must still dedupe across sources."""
    from transform.year_event_calendar.build import (
        _dedupe_weekend_name_collisions,
        _fingerprint_event_name,
    )

    # Alias maps The Open… → US Open… so both share fingerprint "us".
    assert _fingerprint_event_name("The Open Swing Dance Championships") == "us"
    assert _fingerprint_event_name("The Open Swing Dance  Championships") == "us"
    assert _fingerprint_event_name("US Open Swing Dance Championships") == "us"
    # Unaliased stopword-only title: keep content tokens after light strip.
    assert _fingerprint_event_name("The Open Swing Dance Classic") == (
        "open swing dance classic"
    )

    rows = [
        {
            "event_id": 68,
            "name": "The Open Swing Dance  Championships",
            "start_date": date(2026, 11, 25),
            "end_date": date(2026, 11, 29),
            "status": "confirmed",
            "source": "edition_calendar_dates",
            "city": "Los Angeles",
        },
        {
            "event_id": None,
            "name": "The Open Swing Dance  Championships",
            "start_date": date(2026, 11, 25),
            "end_date": date(2026, 11, 29),
            "status": "confirmed",
            "source": "events_list_current",
            "city": "Los Angeles",
        },
    ]
    out = _dedupe_weekend_name_collisions(rows)
    assert len(out) == 1
    assert out[0]["event_id"] == 68
    # Higher source rank keeps list scrape, but inherits catalog event_id.
    assert out[0]["source"] == "events_list_current"


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


def test_calendar_listing_keeps_place_suffix_marketing_title():
    """Catalog stopword-only names must still accept ``Name in City`` listings."""
    from transform.year_event_calendar.build import _calendar_listing_matches_event

    assert _calendar_listing_matches_event("WCS Party", "WCS Party in Vienna")
    assert _calendar_listing_matches_event("WCS Party", "WCS Party")
    assert not _calendar_listing_matches_event("WCS Party", "Soul Flow in Vienna")


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


def test_is_stale_expected_dec_spill_keeps_nye_weekend():
    """Weekday snap may place start in Dec of prior calendar year."""
    from transform.year_event_calendar.expected import is_stale_expected

    start = date(2026, 12, 31)  # Thu spill into prior calendar year
    end = date(2027, 1, 3)  # Sun
    as_of = date(2027, 1, 2)
    # Without event_year: end year 2027 keeps it alive
    assert not is_stale_expected(start=start, end=end, as_of=as_of)
    # Explicit results year also protects Dec spill
    assert not is_stale_expected(
        start=start, end=end, as_of=as_of, event_year=2027
    )
    # Past results year still drops even if dates look current
    assert is_stale_expected(
        start=start, end=end, as_of=as_of, event_year=2026
    )


def test_snap_to_weekday_prefer_year_jan_edge():
    from transform.year_event_calendar.expected import (
        anniversary_date,
        project_start_to_year,
        snap_to_weekday,
    )

    # 2027-01-01 Fri; want Thu → short snap Dec 31 2026; prefer_year flips to Jan 7
    anchor = anniversary_date(date(2026, 1, 1), 2027)
    assert anchor == date(2027, 1, 1)
    snapped = snap_to_weekday(anchor, target_weekday=3, prefer_year=2027)
    assert snapped == date(2027, 1, 7)
    assert snapped.weekday() == 3

    prior = date(2026, 1, 1)  # Thursday
    assert prior.weekday() == 3
    projected = project_start_to_year(prior, 2027)
    assert projected == date(2027, 1, 7)
    assert projected.weekday() == 3
    assert projected.year == 2027


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


def test_rows_from_editions_stats_only_and_results_year(tmp_path):
    from transform.year_event_calendar.build import (
        _rows_from_editions,
        _serialize_event,
    )

    path = tmp_path / "event_editions.csv"
    pd.DataFrame(
        [
            {
                "edition_id": 1,
                "event_id": 221,
                "event_name": "Gateway",
                "event_year": 2025,
                "event_month": 7,
                "edition_date": "2025-07-01",
                "start_date": "",
                "end_date": "",
                "date_source": "edition",
                "calendar_status": "",
                "event_occurred": "",
                "location_id": "",
                "place_city": "",
                "place_state": "",
                "place_country": "",
                "location_raw": "",
                "result_rows": 120,
                "unique_dancers": 50,
                "url": "",
                "typical_location": "",
                "registry_status": "",
            },
            {
                "edition_id": 2,
                "event_id": 42,
                "event_name": "Floorplay",
                "event_year": 2025,
                "event_month": 1,
                "edition_date": "2025-01-01",
                "start_date": "2024-12-27",
                "end_date": "2025-01-01",
                "date_source": "wsdc_calendar",
                "calendar_status": "confirmed",
                "event_occurred": True,
                "location_id": "",
                "place_city": "",
                "place_state": "",
                "place_country": "",
                "location_raw": "",
                "result_rows": 200,
                "unique_dancers": 80,
                "url": "",
                "typical_location": "",
                "registry_status": "",
            },
        ]
    ).to_csv(path, index=False)
    rows = _rows_from_editions(tmp_path)
    by_eid = {r["event_id"]: r for r in rows}
    assert by_eid[221]["stats_only"] is True
    assert by_eid[221]["has_results"] is True
    assert by_eid[221]["year"] == 2025
    assert by_eid[221]["source"] == "event_editions_month_only"
    assert by_eid[42]["stats_only"] is False
    assert by_eid[42]["year"] == 2025
    assert by_eid[42]["start_date"].year == 2024
    ser = _serialize_event(by_eid[221])
    assert ser["stats_only"] is True
    assert ser["has_results"] is True
    assert ser["year"] == 2025


def test_drop_redundant_stats_only_when_day_precision_exists():
    from transform.year_event_calendar.build import _drop_redundant_stats_only

    rows = [
        {
            "event_id": 221,
            "name": "Show Me Showdown",
            "start_date": date(2025, 5, 1),
            "year": 2025,
            "status": "confirmed",
            "stats_only": True,
            "source": "event_editions_month_only",
            "has_results": True,
        },
        {
            "event_id": 221,
            "name": "Show Me Showdown",
            "start_date": date(2025, 5, 15),
            "year": 2025,
            "status": "confirmed",
            "source": "edition_calendar_dates",
            "has_results": True,
        },
        {
            "event_id": 99,
            "name": "Only Stats",
            "start_date": date(2025, 6, 1),
            "year": 2025,
            "status": "confirmed",
            "stats_only": True,
            "has_results": True,
        },
    ]
    out = _drop_redundant_stats_only(rows)
    assert len(out) == 2
    assert {r["event_id"] for r in out} == {221, 99}
    assert not any(r.get("stats_only") and r["event_id"] == 221 for r in out)


def test_dedupe_prefers_day_dates_over_stats_only():
    from transform.year_event_calendar.build import _dedupe_rows

    rows = [
        {
            "event_id": 221,
            "name": "Gateway",
            "start_date": date(2025, 7, 1),
            "end_date": None,
            "status": "confirmed",
            "source": "event_editions_month_only",
            "year": 2025,
            "stats_only": True,
            "has_results": True,
        },
        {
            "event_id": 221,
            "name": "Gateway",
            "start_date": date(2025, 7, 3),
            "end_date": date(2025, 7, 6),
            "status": "confirmed",
            "source": "edition_calendar_dates",
            "year": 2025,
            "has_results": True,
        },
    ]
    # Different weekends — both kept
    out = _dedupe_rows(rows)
    assert len(out) == 2

    same_weekend = [
        rows[0],
        {
            **rows[1],
            "start_date": date(2025, 7, 1),
            "end_date": date(2025, 7, 4),
        },
    ]
    merged = _dedupe_rows(same_weekend)
    assert len(merged) == 1
    assert merged[0].get("stats_only") is not True
    assert merged[0]["source"] == "edition_calendar_dates"
    assert merged[0]["has_results"] is True


def test_series_linked_ids_bidirectional():
    from transform.year_event_calendar.build import _series_linked_ids

    # Successor map empty after single-id merges; identity is the id itself.
    assert _series_linked_ids(264) == {264}
    assert _series_linked_ids(493) == {493}
    assert _series_linked_ids(999) == {999}


def test_apply_year_aware_series_names_uptown_and_show_me():
    from transform.year_event_calendar.build import _apply_year_aware_series_names

    rows = [
        {
            "event_id": 264,
            "name": "Swedish Swing Summer Camp",
            "year": 2025,
            "start_date": date(2025, 8, 15),
            "status": "confirmed",
        },
        {
            "event_id": 493,
            "name": "UpTown Swing",
            "year": 2025,
            "start_date": date(2025, 8, 15),
            "status": "confirmed",
        },
        {
            "event_id": 221,
            "name": "Gateway Swing Classic",
            "year": 2025,
            "start_date": date(2025, 5, 15),
            "status": "confirmed",
        },
        {
            "event_id": 221,
            "name": "Show Me Showdown",
            "year": 2026,
            "start_date": date(2026, 5, 14),
            "status": "confirmed",
        },
    ]
    _apply_year_aware_series_names(rows)
    assert rows[0]["name"] == "UpTown Swing"
    assert rows[0]["event_id"] == 264
    # 493 is not in the split id list until MERGE; name still matches sources → UpTown@264
    assert rows[1]["name"] == "UpTown Swing"
    assert rows[1]["event_id"] == 264
    assert rows[2]["name"] == "Show Me Showdown"
    assert rows[2]["event_id"] == 221
    assert rows[3]["name"] == "Gateway Swing Classic"
    assert rows[3]["event_id"] == 221


def test_ids_blocked_by_terminal_expands_series_links():
    from transform.year_event_calendar.build import _ids_blocked_by_terminal

    rows = [
        {
            "event_id": 264,
            "start_date": date(2025, 8, 14),
            "year": 2025,
            "status": "hiatus",
            "name": "UpTown Swing",
        },
        {
            "event_id": 264,
            "start_date": date(2024, 8, 15),
            "year": 2024,
            "status": "confirmed",
            "name": "UpTown Swing",
        },
    ]
    blocked = _ids_blocked_by_terminal(rows, before_year=2026)
    assert 264 in blocked
    assert 493 not in blocked  # ghost merged away; no successor expansion

def test_operator_overrides_emit_soul_flow_hiatus_and_expected():
    from transform.knowledge.calendar_operator_overrides import (
        SOUL_FLOW_PROVISIONAL_EVENT_ID,
    )
    from transform.year_event_calendar.build import _rows_from_operator_overrides

    rows = _rows_from_operator_overrides()
    by_year = {
        (r["event_id"], r["year"]): r
        for r in rows
        if r["event_id"] == SOUL_FLOW_PROVISIONAL_EVENT_ID
    }
    assert by_year[(SOUL_FLOW_PROVISIONAL_EVENT_ID, 2026)]["status"] == "hiatus"
    assert by_year[(SOUL_FLOW_PROVISIONAL_EVENT_ID, 2027)]["status"] == "expected"
    assert by_year[(SOUL_FLOW_PROVISIONAL_EVENT_ID, 2026)]["country"] == "France"
    assert by_year[(SOUL_FLOW_PROVISIONAL_EVENT_ID, 2026)]["source"] == "operator_override"


def test_city_from_location_raw_first_segment():
    from transform.year_event_calendar.build import _city_from_location_raw

    assert _city_from_location_raw("Dallas, TX, United States") == "Dallas"
    assert _city_from_location_raw(None) is None
    assert _city_from_location_raw("nan") is None


def test_correct_ucwdc_worlds_remaps_152_championships_to_75():
    from transform.year_event_calendar.build import _correct_ucwdc_worlds_event_ids

    rows = [
        {
            "event_id": 152,
            "name": "UCWDC Country Dance World Championships",
            "city": "Dallas",
        },
        {
            "event_id": 152,
            "name": "Worlds UCWDC",
            "city": "Orlando",
        },
    ]
    _correct_ucwdc_worlds_event_ids(rows)
    assert rows[0]["event_id"] == 75
    assert rows[0]["name"] == "UCWDC Country Dance World Championship"
    assert rows[1]["event_id"] == 152
    assert rows[1]["name"] == "Worlds UCWDC"


def test_serialize_event_unique_ids_for_unlinked_trials_same_start():
    """Two trial rows with null event_id on the same day must not share ``id``."""
    from transform.year_event_calendar.build import _serialize_event

    base = {
        "start_date": date(2026, 8, 21),
        "end_date": date(2026, 8, 23),
        "event_id": None,
        "status": "confirmed",
        "kind": "trial",
        "year": 2026,
        "source": "scheduled_events",
        "url": None,
        "lat": None,
        "lon": None,
    }
    a = _serialize_event(
        {
            **base,
            "name": "Manneken Swing",
            "city": "Bruxelles",
            "country": "Belgium",
        }
    )
    b = _serialize_event(
        {
            **base,
            "name": "Westie Joy",
            "city": "Bucharest",
            "country": "Romania",
        }
    )
    assert a["id"] != b["id"]
    assert a["id"] == "confirmed:t-manneken-swing-bruxelles-belgium:2026-08-21"
    assert b["id"] == "confirmed:t-westie-joy-bucharest-romania:2026-08-21"
    linked = _serialize_event(
        {
            **base,
            "event_id": 135,
            "name": "Desert City Swing",
            "city": "Phoenix",
            "country": "United States",
        }
    )
    assert linked["id"] == "confirmed:135:2026-08-21"
    diacritic = _serialize_event(
        {
            **base,
            "name": "Cologne Calling WCS",
            "city": "Köln",
            "country": "Germany",
        }
    )
    assert diacritic["id"] == "confirmed:t-cologne-calling-wcs-koln-germany:2026-08-21"
    # Numeric-only slug must not collide with a real event_id token.
    numeric_name = _serialize_event(
        {
            **base,
            "name": "135",
            "city": "",
            "country": "",
        }
    )
    assert numeric_name["id"] == "confirmed:t-135:2026-08-21"
    assert numeric_name["id"] != linked["id"]


def test_cancelled_calendar_status_coerced_to_hiatus():
    from transform.year_event_calendar.build import (
        STATUS_CANCELLED,
        STATUS_HIATUS,
        _coerce_cancelled_to_hiatus,
        _norm_status_calendar,
    )

    assert _norm_status_calendar("cancelled") == STATUS_HIATUS
    assert _norm_status_calendar("canceled") == STATUS_HIATUS
    assert _norm_status_calendar("hiatus") == STATUS_HIATUS
    rows = [{"status": STATUS_CANCELLED, "name": "Swing Dance America"}]
    _coerce_cancelled_to_hiatus(rows)
    assert rows[0]["status"] == STATUS_HIATUS


def test_build_uses_events_list_fallback_when_scheduled_export_empty(tmp_path):
    from transform.year_event_calendar.build import build_year_event_calendar

    (tmp_path / "scheduled_events.csv").write_text(
        "schedule_event_key,source_fingerprint,canonical_event_id,event_name,start_date,end_date,results_year,results_month,status_event,registry_trial_status,location_raw,country,url,confirmed,canceled,on_hiatus\n",
        encoding="utf-8",
    )
    events_list_dir = tmp_path / "events_list"
    events_list_dir.mkdir(parents=True, exist_ok=True)
    (events_list_dir / "current.json").write_text(
        """
{
  "events": [
    {
      "source_fingerprint": "trial-2026-a",
      "event_name": "Autumn Beat Trial Event",
      "start_date": "2026-10-02",
      "end_date": "2026-10-05",
      "results_year": 2026,
      "status_event": "Trial Event",
      "location_raw": "Warsaw, Poland",
      "country": "Poland",
      "url": "https://example.com/autumn",
      "confirmed": true,
      "canceled": false,
      "on_hiatus": false
    },
    {
      "source_fingerprint": "trial-2027-a",
      "event_name": "Swing Valley Trial Event",
      "start_date": "2027-07-01",
      "end_date": "2027-07-04",
      "results_year": 2027,
      "status_event": "Trial Event",
      "location_raw": "Prague, Czechia",
      "country": "Czechia",
      "url": "https://example.com/valley",
      "confirmed": true,
      "canceled": false,
      "on_hiatus": false
    }
  ]
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    payload = build_year_event_calendar(tmp_path, as_of=date(2026, 8, 5), year_radius=2)
    trials = [
        e for e in payload["events"]
        if e["kind"] == "trial" and e["year"] in {2026, 2027}
    ]
    assert any(e["name"] == "Autumn Beat Trial Event" for e in trials)
    assert any(e["name"] == "Swing Valley Trial Event" for e in trials)

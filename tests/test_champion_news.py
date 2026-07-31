"""Tests for Champion News detection and merge."""

from __future__ import annotations

from datetime import date

from transform.champion_news.detect import (
    ResultEvent,
    _accumulate_crossing,
    make_transition_slug,
)
from transform.champion_news.merge import merge_champion_news
from transform.champion_news.path import build_champion_path
from transform.champion_news.thresholds import (
    PATHWAY_ALS_225,
    PATHWAY_CHMP_10,
    STATUS_ALLOWED,
    STATUS_REQUIRED,
)


def _ev(
    *,
    year: int,
    month: int,
    points: float,
    division: str,
    name: str = "Test Event",
    day: int | None = None,
    country: str = "France",
) -> ResultEvent:
    start = date(year, month, day or 1) if day else None
    return ResultEvent(
        dancer_id="1",
        role="leader",
        event_name=name,
        event_year=year,
        event_month=month,
        event_points=points,
        division=division,
        location_id="1",
        start_date=start,
        end_date=start,
        place_city="Paris",
        place_country=country,
        location_display="Paris, France",
    )


def test_allowed_at_150_als():
    events = [
        _ev(year=2024, month=1, points=100, division="ALS", name="A"),
        _ev(year=2026, month=7, points=50, division="ALS", name="B", day=28),
    ]
    allowed, required = _accumulate_crossing(events)
    assert allowed is not None
    assert allowed["status"] == STATUS_ALLOWED
    assert allowed["als_total"] == 150
    assert allowed["threshold_event"] == "B"
    assert required is None


def test_required_via_als_225():
    events = [
        _ev(year=2024, month=1, points=150, division="ALS", name="A"),
        _ev(year=2026, month=7, points=75, division="ALS", name="B", day=29),
    ]
    allowed, required = _accumulate_crossing(events)
    assert allowed is not None
    assert required is not None
    assert required["status"] == STATUS_REQUIRED
    assert required["required_pathway"] == PATHWAY_ALS_225
    assert required["als_total"] == 225


def test_required_via_chmp_10():
    events = [
        _ev(year=2024, month=1, points=150, division="ALS", name="A"),
        _ev(year=2026, month=7, points=10, division="CHMP", name="C", day=30),
    ]
    allowed, required = _accumulate_crossing(events)
    assert allowed is not None
    assert required is not None
    assert required["required_pathway"] == PATHWAY_CHMP_10
    assert required["chmp_total"] == 10


def test_same_month_ordering_by_start_date():
    # Alphabetical-only order would process "A Late" before "Z Early" and assign
    # Allowed to the wrong event. Day-level start_date must win.
    events = [
        _ev(year=2026, month=7, points=100, division="ALS", name="A Late", day=20),
        _ev(year=2026, month=7, points=50, division="ALS", name="Z Early", day=10),
    ]
    allowed, _ = _accumulate_crossing(events)
    assert allowed is not None
    assert allowed["threshold_event"] == "A Late"
    assert allowed["threshold_date"] == "2026-07-20"
    assert allowed["als_total"] == 150


def test_required_prefers_als_when_both_paths_same_edition():
    events = [
        _ev(year=2024, month=1, points=200, division="ALS", name="Prior"),
        _ev(year=2024, month=1, points=5, division="CHMP", name="Prior"),
        _ev(year=2026, month=7, points=30, division="ALS", name="Both", day=28),
        _ev(year=2026, month=7, points=5, division="CHMP", name="Both", day=28),
    ]
    _, required = _accumulate_crossing(events)
    assert required is not None
    assert required["required_pathway"] == PATHWAY_ALS_225
    assert required["als_total"] >= 225
    assert required["chmp_total"] >= 10


def test_edition_dates_fill_from_scheduled_events(tmp_path):
    from transform.champion_news.detect import load_edition_dates

    editions = tmp_path / "event_editions.csv"
    editions.write_text(
        "event_name,event_year,event_month,start_date,end_date,place_city,place_country,location_raw\n"
        "Sea Sun and Swing,2026,7,,,La Grande Motte,France,\n",
        encoding="utf-8",
    )
    schedule = tmp_path / "scheduled_events.csv"
    schedule.write_text(
        "canonical_name,event_name,results_year,results_month,start_date,end_date\n"
        "Sea Sun and Swing,Sea Sun and Swing,2026,7,2026-07-25,2026-07-27\n",
        encoding="utf-8",
    )
    loaded = load_edition_dates(editions, schedule_path=schedule)
    start, end, city, country, _ = loaded[("sea sun and swing", 2026, 7)]
    assert start == date(2026, 7, 25)
    assert end == date(2026, 7, 27)
    assert city == "La Grande Motte"
    assert country == "France"



def test_merge_preserves_notes():
    existing = {
        "summaries": [
            {
                "post_date": "2026-07-30",
                "events_count": 1,
                "events": [
                    {
                        "slug": "2026-07-30-1-leader-allowed",
                        "dancer_id": "1",
                        "role": "leader",
                        "status": "allowed",
                        "notes": "manual fix",
                        "als_total": 150,
                    }
                ],
            }
        ]
    }
    candidates = [
        {
            "slug": "2026-07-30-1-leader-allowed",
            "dancer_id": "1",
            "role": "leader",
            "status": "allowed",
            "als_total": 151,
            "path": {"event_counts": {"total": 2}},
        }
    ]
    payload, report = merge_champion_news(
        existing, candidates, today=date(2026, 7, 31)
    )
    assert report["updated_count"] == 1
    assert report["post_date"] == "2026-07-31"
    ev = payload["summaries"][0]["events"][0]
    assert ev["notes"] == "manual fix"
    assert ev["als_total"] == 151


def test_required_via_chmp_10_without_prior_allowed():
    """Champions-only Required when ALS never reaches 150."""
    events = [
        _ev(year=2024, month=1, points=40, division="ALS", name="A"),
        _ev(year=2026, month=7, points=10, division="CHMP", name="C", day=30),
    ]
    allowed, required = _accumulate_crossing(events)
    assert allowed is None
    assert required is not None
    assert required["required_pathway"] == PATHWAY_CHMP_10
    assert required["chmp_total"] == 10
    assert required["als_total"] == 40


def test_path_counts_and_tops():
    events = [
        _ev(year=2024, month=1, points=40, division="ALS", name="One"),
        _ev(year=2025, month=2, points=60, division="ALS", name="Two"),
        _ev(year=2026, month=3, points=5, division="CHMP", name="Three"),
    ]
    path = build_champion_path(events)
    assert path["event_counts"]["total"] == 3
    assert path["event_counts"]["all_stars"] == 2
    assert path["event_counts"]["champions"] == 1
    assert path["top_events"][0]["event_name"] == "Two"
    assert path["first_points"]["event_name"] == "One"


def test_merge_preserves_telegram_metadata():
    existing = {
        "summaries": [
            {
                "post_date": "2026-07-31",
                "events_count": 1,
                "events": [
                    {
                        "slug": "2026-07-25-1-leader-allowed",
                        "dancer_id": "1",
                        "role": "leader",
                        "status": "allowed",
                        "notes": "Backfill from Telegram",
                        "telegram_msg_id": 216,
                        "probe": False,
                        "als_total": 150,
                    }
                ],
            }
        ]
    }
    candidates = [
        {
            "slug": "2026-07-25-1-leader-allowed",
            "dancer_id": "1",
            "role": "leader",
            "status": "allowed",
            "als_total": 152,
            "path": {"event_counts": {"total": 3}},
        }
    ]
    payload, report = merge_champion_news(
        existing, candidates, today=date(2026, 8, 1)
    )
    assert report["updated_count"] == 1
    ev = payload["summaries"][0]["events"][0]
    assert ev["als_total"] == 152
    assert ev["notes"] == "Backfill from Telegram"
    assert ev["telegram_msg_id"] == 216
    assert ev["probe"] is False


def test_path_as_of_excludes_later_champions():
    events = [
        _ev(year=2025, month=6, points=10, division="ALS", name="ALS Event"),
        _ev(
            year=2026,
            month=7,
            day=2,
            points=6,
            division="CHMP",
            name="Wild Wild Westie",
        ),
    ]
    full = build_champion_path(events)
    assert full["event_counts"]["champions"] == 1
    assert full["event_counts"]["total"] == 2

    as_of = build_champion_path(events, as_of=date(2026, 6, 17))
    assert as_of["event_counts"]["champions"] == 0
    assert as_of["event_counts"]["all_stars"] == 1
    assert as_of["event_counts"]["total"] == 1
    assert as_of["top_events"][0]["event_name"] == "ALS Event"

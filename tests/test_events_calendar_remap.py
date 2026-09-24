"""Tests for remapping stale edition_calendar_dates event_ids."""

from __future__ import annotations

import pandas as pd

from transform.events_calendar_remap import plan_calendar_event_id_remaps


def test_plan_remaps_swinglab_stale_event_id():
    calendar = pd.DataFrame(
        [
            {
                "event_id": "389",
                "event_year": "2026",
                "event_month": "7",
                "calendar_title": "SwingLab Berlin",
            }
        ]
    )
    editions = pd.DataFrame(
        [
            {
                "event_id": "396",
                "event_name": "SwingLab Berlin",
                "event_year": "2026",
                "event_month": "7",
            }
        ]
    )
    remaps = plan_calendar_event_id_remaps(calendar, editions)
    assert remaps == [
        {
            "old_event_id": "389",
            "new_event_id": "396",
            "event_year": 2026,
            "event_month": 7,
            "calendar_title": "SwingLab Berlin",
        }
    ]


def test_plan_remaps_skips_already_correct_and_ambiguous():
    calendar = [
        {
            "event_id": "396",
            "event_year": 2026,
            "event_month": 7,
            "calendar_title": "SwingLab Berlin",
        },
        {
            "event_id": "1",
            "event_year": 2026,
            "event_month": 6,
            "calendar_title": "Mystery Ball",
        },
    ]
    editions = pd.DataFrame(
        [
            {
                "event_id": "396",
                "event_name": "SwingLab Berlin",
                "event_year": 2026,
                "event_month": 7,
            },
            {
                "event_id": "10",
                "event_name": "Mystery Ball",
                "event_year": 2026,
                "event_month": 6,
            },
            {
                "event_id": "11",
                "event_name": "Mystery Ball",
                "event_year": 2026,
                "event_month": 6,
            },
        ]
    )
    assert plan_calendar_event_id_remaps(calendar, editions) == []


def test_plan_merge_map_remaps_paris_swing_ghosts():
    from transform.events_calendar_remap import plan_merge_map_calendar_remaps

    calendar = pd.DataFrame(
        [
            {
                "event_id": "307",
                "event_year": 2027,
                "event_month": 3,
                "calendar_title": "Paris Swing Classic",
            },
            {
                "event_id": "543",
                "event_year": 2027,
                "event_month": 3,
                "calendar_title": "Paris Swing Classic",
            },
            {
                "event_id": "272",
                "event_year": 2027,
                "event_month": 3,
                "calendar_title": "Paris Swing Classic",
            },
        ]
    )
    remaps = plan_merge_map_calendar_remaps(calendar)
    assert {
        (r["old_event_id"], r["new_event_id"], r["event_year"], r["event_month"])
        for r in remaps
    } == {("307", "272", 2027, 3), ("543", "272", 2027, 3)}


def test_plan_merge_map_remaps_ggp_paris_ghost_to_reunion_id():
    from transform.events_calendar_remap import plan_merge_map_calendar_remaps
    from transform.knowledge.event_aliases import MERGE_EVENT_ID_MAP

    assert MERGE_EVENT_ID_MAP[409] == 342
    assert MERGE_EVENT_ID_MAP[437] == 342
    assert MERGE_EVENT_ID_MAP[438] == 342
    calendar = pd.DataFrame(
        [
            {
                "event_id": "409",
                "event_year": 2026,
                "event_month": 9,
                "calendar_title": "Global Grand Prix -- West Coast Swing Championships",
            }
        ]
    )
    remaps = plan_merge_map_calendar_remaps(calendar)
    assert remaps == [
        {
            "old_event_id": "409",
            "new_event_id": "342",
            "event_year": 2026,
            "event_month": 9,
            "calendar_title": "Global Grand Prix -- West Coast Swing Championships",
        }
    ]


def test_plan_mismatched_title_deletes_soul_flow_on_ggp():
    from transform.events_calendar_remap import plan_mismatched_title_calendar_deletes

    calendar = pd.DataFrame(
        [
            {
                "event_id": "342",
                "event_year": 2026,
                "event_month": 12,
                "event_name": "Global Grand Prix - West Coast Swing Reunion",
                "calendar_title": "Soul Flow - West Coast Swing Festival (Hiatus -- 2026)",
                "match_via": "url",
            },
            {
                "event_id": "342",
                "event_year": 2025,
                "event_month": 12,
                "event_name": "Global Grand Prix - West Coast Swing Reunion",
                "calendar_title": "Global Grand Prix - West Coast Swing Championships",
                "match_via": "url",
            },
            {
                # Name-based near-match — do not purge (year calendar filters).
                "event_id": "261",
                "event_year": 2027,
                "event_month": 6,
                "event_name": "Neverland Swing",
                "calendar_title": "NeverlandSwing Dutch Swing Championships 2027",
                "match_via": "name",
            },
        ]
    )
    deletes = plan_mismatched_title_calendar_deletes(calendar)
    assert len(deletes) == 1
    assert deletes[0]["event_id"] == "342"
    assert deletes[0]["event_year"] == 2026
    assert deletes[0]["event_month"] == 12

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

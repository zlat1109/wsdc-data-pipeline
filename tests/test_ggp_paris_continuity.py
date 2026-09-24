"""Regression: Global Grand Prix Toulouse→Paris vs Soul Flow split survives re-parse."""

from __future__ import annotations

import pandas as pd

from transform.events_calendar_match import match_calendar_to_editions
from transform.events_calendar_normalize import normalize_calendar_events
from transform.events_calendar_remap import (
    plan_merge_map_calendar_remaps,
    plan_mismatched_title_calendar_deletes,
)
from transform.geography.geo_event import RELOCATION_MERGE_PAIRS, classify_event_id_pair, geo_key
from transform.knowledge.calendar_operator_overrides import SOUL_FLOW_PROVISIONAL_EVENT_ID
from transform.knowledge.event_aliases import MERGE_EVENT_ID_MAP
from transform.knowledge.events import KNOWN_EVENT_METADATA
from transform.year_event_calendar.build import _resolve_merge_event_id


GGP_URL = "https://www.globalgrandprixwcs.com/"
GGP_NAME = "Global Grand Prix - West Coast Swing Reunion"
CHAMP_NAME = "Global Grand Prix -- West Coast Swing Championships"
SOUL_FLOW_TITLE = "Soul Flow - West Coast Swing Festival (Hiatus -- 2026)"


def test_merge_map_and_relocation_cover_all_ggp_ghosts():
    for ghost in (409, 437, 438):
        assert MERGE_EVENT_ID_MAP[ghost] == 342
        assert frozenset({342, ghost}) in RELOCATION_MERGE_PAIRS
        assert classify_event_id_pair(
            ghost,
            342,
            geo_key("Paris", "", "France"),
            geo_key("Toulouse", "", "France"),
        ) == "merge_candidate"
    assert _resolve_merge_event_id(409) == 342
    assert KNOWN_EVENT_METADATA[342]["name"] == GGP_NAME


def test_next_calendar_parse_does_not_stick_soul_flow_on_ggp():
    """Simulate post-merge catalog: 342=GGP, 990001=Soul Flow, shared URL."""
    cal = normalize_calendar_events(
        [
            {
                "title": CHAMP_NAME,
                "start": "2026-09-18",
                "end": "2026-09-22",
                "url": GGP_URL,
            },
            {
                "title": SOUL_FLOW_TITLE,
                "start": "2026-12-11",
                "end": "2026-12-14",
                "url": GGP_URL,
            },
        ],
        min_start=None,
    )
    editions = pd.DataFrame(
        [
            {
                "edition_id": "e342-2025",
                "event_id": "342",
                "event_name": GGP_NAME,
                "event_year": "2025",
                "event_month": "12",
            },
            {
                "edition_id": "e342-2026",
                "event_id": "342",
                "event_name": CHAMP_NAME,
                "event_year": "2026",
                "event_month": "9",
            },
        ]
    )
    catalog = pd.DataFrame(
        [
            {"event_id": "342", "canonical_name": GGP_NAME, "url": GGP_URL},
            {
                "event_id": str(SOUL_FLOW_PROVISIONAL_EVENT_ID),
                "canonical_name": "Soul Flow - West Coast Swing Festival",
                "url": GGP_URL,
            },
        ]
    )
    rows, _summary = match_calendar_to_editions(cal, editions, catalog)
    by_title = {r["event_name"]: r for r in rows}

    champ = by_title[CHAMP_NAME]
    assert champ["matched_event_id"] == "342"
    assert champ["match_status"] == "matched"

    soul = by_title["Soul Flow - West Coast Swing Festival"]
    assert soul["matched_event_id"] == str(SOUL_FLOW_PROVISIONAL_EVENT_ID)
    assert soul["match_status"] == "event_only"


def test_enrich_remap_and_purge_plan_after_scrape_regression():
    """Durable enrich step: 409→342 remap + Soul Flow URL hijack delete."""
    calendar = pd.DataFrame(
        [
            {
                "event_id": "409",
                "event_year": 2026,
                "event_month": 9,
                "calendar_title": CHAMP_NAME,
                "event_name": CHAMP_NAME,
                "match_via": "url",
            },
            {
                "event_id": "342",
                "event_year": 2026,
                "event_month": 12,
                "calendar_title": SOUL_FLOW_TITLE,
                "event_name": GGP_NAME,
                "match_via": "url",
            },
            {
                "event_id": str(SOUL_FLOW_PROVISIONAL_EVENT_ID),
                "event_year": 2026,
                "event_month": 12,
                "calendar_title": SOUL_FLOW_TITLE,
                "event_name": "Soul Flow - West Coast Swing Festival",
                "match_via": "operator_assumption",
            },
        ]
    )
    remaps = plan_merge_map_calendar_remaps(calendar)
    assert remaps == [
        {
            "old_event_id": "409",
            "new_event_id": "342",
            "event_year": 2026,
            "event_month": 9,
            "calendar_title": CHAMP_NAME,
        }
    ]
    deletes = plan_mismatched_title_calendar_deletes(calendar)
    assert len(deletes) == 1
    assert deletes[0]["event_id"] == "342"
    assert deletes[0]["event_month"] == 12

"""Tests for Todd Event Editions → DWH enrichment."""

from __future__ import annotations

import pandas as pd

from transform.event_editions.build import build_ee_tables
from transform.event_editions.keys import parse_todd_edition_id
from transform.event_editions.match import match_edition
from transform.event_editions.metros import build_metros
from transform.event_editions.venues import build_venues, normalize_venue_name
from transform.event_editions.officials import build_officials, normalize_person_name
from transform.event_editions.gate import reconcile


DECISIONS = {
    "class_rules": [
        {
            "class": "status_history_absent_from_core",
            "action": "load_status_history",
        },
        {"class": "future_scheduled_skip", "action": "skip"},
        {"class": "value_mismatch_core_wins", "action": "acknowledge", "winner": "core"},
    ],
    "cases": [],
}


def test_parse_todd_edition_id():
    k = parse_todd_edition_id("wsdc:31:November 2026")
    assert k is not None
    assert k.wsdc_event_id == 31
    assert k.event_year == 2026
    assert k.event_month == 11
    assert parse_todd_edition_id("eepro:123") is None


def test_match_exact_and_merge_map():
    keys = {(31, 2026, 11), (47, 2024, 7)}
    m = match_edition("wsdc:31:November 2026", core_keys=keys)
    assert m["match_kind"] == "exact"
    assert m["event_id"] == 31
    # 466 → 47 in MERGE_EVENT_ID_MAP
    from transform.knowledge.event_aliases import MERGE_EVENT_ID_MAP

    raw = next(k for k, v in MERGE_EVENT_ID_MAP.items() if v == 47)
    m2 = match_edition(f"wsdc:{raw}:July 2024", core_keys=keys)
    assert m2["match_kind"] == "merge_map"
    assert m2["event_id"] == 47


def test_normalize_venue_name():
    assert normalize_venue_name("Brookstreet Hotel") == "brookstreet"
    assert normalize_venue_name("  Foo   Resort ") == "foo"


def test_normalize_person_name():
    assert normalize_person_name("Jane  Q. Doe") == "jane q doe"


def test_build_ee_tables_occurred_and_status():
    df = pd.DataFrame(
        [
            {
                "event_edition_id": "wsdc:31:November 2026",
                "wsdc_event_id": "31",
                "event_series_id": "31",
                "edition_status": "occurred",
                "wsdc_event_name": "Mountain Magic",
                "registry_status": "registry",
                "scoring_software": "scoring.dance",
                "coordinates_precision": "venue",
                "date_precision": "day",
                "accommodation_hotel": None,
                "row_info": "{}",
                "cancelled_covid": False,
                "event_edition_name": "Mountain Magic",
                "start_date": "2026-11-05",
                "end_date": "2026-11-08",
                "city": "South Lake Tahoe",
                "region": "NV",
                "country": "United States",
                "metro": "Reno",
                "latitude": 39.0,
                "longitude": -120.0,
                "venue_name": "Lake Tahoe Resort",
                "venue_address": "1 Main St",
                "venue_type": "Hotel",
                "venue_url": None,
                "chief_judge": "Alice Judge",
                "scoreperson": None,
                "judges": ["Bob Panel"],
                "judge_rounds": ["prelim"],
            },
            {
                "event_edition_id": "wsdc:31:November 2020",
                "wsdc_event_id": "31",
                "event_series_id": "31",
                "edition_status": "cancelled",
                "wsdc_event_name": "Mountain Magic",
                "registry_status": "registry",
                "scoring_software": None,
                "coordinates_precision": None,
                "date_precision": "day",
                "accommodation_hotel": None,
                "row_info": None,
                "cancelled_covid": True,
                "event_edition_name": "Mountain Magic",
                "start_date": "2020-11-05",
                "end_date": None,
                "city": "South Lake Tahoe",
                "region": "NV",
                "country": "United States",
                "metro": "Reno",
                "latitude": None,
                "longitude": None,
                "venue_name": None,
                "venue_address": None,
                "venue_type": None,
                "venue_url": None,
                "chief_judge": None,
                "scoreperson": None,
                "judges": None,
                "judge_rounds": None,
            },
            {
                "event_edition_id": "wsdc:31:November 2027",
                "wsdc_event_id": "31",
                "event_series_id": "31",
                "edition_status": "scheduled",
                "wsdc_event_name": "Mountain Magic",
                "registry_status": None,
                "scoring_software": None,
                "coordinates_precision": None,
                "date_precision": None,
                "accommodation_hotel": None,
                "row_info": None,
                "cancelled_covid": None,
                "event_edition_name": "Mountain Magic",
                "start_date": "2027-11-04",
                "end_date": None,
                "city": None,
                "region": None,
                "country": None,
                "metro": None,
                "latitude": None,
                "longitude": None,
                "venue_name": None,
                "venue_address": None,
                "venue_type": None,
                "venue_url": None,
                "chief_judge": None,
                "scoreperson": None,
                "judges": None,
                "judge_rounds": None,
            },
            {
                "event_edition_id": "eepro:skip",
                "wsdc_event_id": None,
                "event_series_id": None,
                "edition_status": "occurred",
                "wsdc_event_name": "Non WSDC",
                "registry_status": "not_wsdc",
                "scoring_software": None,
                "coordinates_precision": None,
                "date_precision": None,
                "accommodation_hotel": None,
                "row_info": None,
                "cancelled_covid": None,
                "event_edition_name": "Non WSDC",
                "start_date": None,
                "end_date": None,
                "city": None,
                "region": None,
                "country": None,
                "metro": None,
                "latitude": None,
                "longitude": None,
                "venue_name": None,
                "venue_address": None,
                "venue_type": None,
                "venue_url": None,
                "chief_judge": None,
                "scoreperson": None,
                "judges": None,
                "judge_rounds": None,
            },
        ]
    )
    core = [{"event_id": 31, "event_year": 2026, "event_month": 11}]
    tables = build_ee_tables(
        df,
        core_editions=core,
        decisions=DECISIONS,
        locations=[
            {
                "location_id": 1,
                "event_city": "South Lake Tahoe",
                "event_state": "NV",
                "event_country": "United States",
            }
        ],
        dancers=[{"dancer_id": 99, "first_name": "Alice", "last_name": "Judge"}],
        include_metros_venues=True,
        include_officials=True,
    )
    assert tables.gate["ok"] is True
    assert len(tables.attributes) == 1
    assert tables.attributes[0]["event_id"] == 31
    assert tables.attributes[0]["scoring_software"] == "scoring.dance"
    assert tables.attributes[0]["venue_id"] is not None
    assert len(tables.status_history) == 1
    assert tables.status_history[0]["edition_status"] == "cancelled"
    assert tables.status_history[0]["cancelled_covid"] is True
    assert tables.stats["skipped_scheduled"] == 1
    assert len(tables.metros) >= 1
    assert len(tables.venues) == 1
    assert any(o["canonical_name"] == "Alice Judge" for o in tables.officials)
    assert any(b["role"] == "chief_judge" for b in tables.edition_officials)


def test_gate_blocks_occurred_missing():
    todd = [
        {
            "todd_edition_id": "wsdc:99:January 2024",
            "edition_status": "occurred",
            "wsdc_event_id": 99,
            "event_series_id": "99",
        }
    ]
    matches = [
        {
            "todd_edition_id": "wsdc:99:January 2024",
            "event_id": 99,
            "event_year": 2024,
            "event_month": 1,
            "match_kind": "unmatched",
            "canonical_event_id": 99,
        }
    ]
    report = reconcile(
        todd_rows=todd,
        matches=matches,
        core_keys=set(),
        decisions=DECISIONS,
    )
    assert report["ok"] is False
    assert any(i["class"] == "occurred_missing_from_core" for i in report["issues"])


def test_metros_link_locations():
    todd = [
        {
            "metro": "Boston",
            "city": "Waltham",
            "region": "MA",
            "country": "United States",
            "latitude": 42.3,
            "longitude": -71.2,
        }
    ]
    locs = [
        {
            "location_id": 10,
            "event_city": "Waltham",
            "event_state": "MA",
            "event_country": "United States",
        }
    ]
    metros, links = build_metros(todd, locations=locs)
    assert len(metros) == 1
    assert links[0]["location_id"] == 10


def test_venues_dedup():
    todd = [
        {
            "todd_edition_id": "wsdc:1:January 2024",
            "venue_name": "Brookstreet Hotel",
            "venue_address": "1 Main",
            "venue_type": "Hotel",
            "venue_url": None,
            "coordinates_precision": "venue",
            "latitude": 1.0,
            "longitude": 2.0,
            "city": "Ottawa",
            "region": "ON",
            "country": "Canada",
        },
        {
            "todd_edition_id": "wsdc:1:January 2025",
            "venue_name": "Brookstreet",
            "venue_address": "1 Main",
            "venue_type": "Hotel",
            "venue_url": None,
            "coordinates_precision": "city",
            "latitude": 1.1,
            "longitude": 2.1,
            "city": "Ottawa",
            "region": "ON",
            "country": "Canada",
        },
    ]
    venues, by_todd = build_venues(todd, locations=[])
    assert len(venues) == 1
    assert by_todd["wsdc:1:January 2024"] == by_todd["wsdc:1:January 2025"]


def _blank_todd(**overrides):
    base = {
        "wsdc_event_id": "31",
        "event_series_id": "31",
        "edition_status": "occurred",
        "wsdc_event_name": "X",
        "registry_status": None,
        "scoring_software": None,
        "coordinates_precision": None,
        "date_precision": "day",
        "accommodation_hotel": None,
        "row_info": None,
        "cancelled_covid": None,
        "event_edition_name": "X",
        "start_date": "2026-11-05",
        "end_date": "2026-11-08",
        "city": "Tahoe",
        "region": "NV",
        "country": "United States",
        "metro": None,
        "latitude": None,
        "longitude": None,
        "venue_name": None,
        "venue_address": None,
        "venue_type": None,
        "venue_url": None,
        "chief_judge": None,
        "scoreperson": None,
        "judges": None,
        "judge_rounds": None,
    }
    base.update(overrides)
    return base


def test_natural_key_collision_prefers_exact():
    """merge_map + exact for same month → keep exact todd_edition_id."""
    from transform.knowledge.event_aliases import MERGE_EVENT_ID_MAP

    # Pick a real merge that targets an id we put in core_keys
    raw, canon = next(iter(MERGE_EVENT_ID_MAP.items()))
    df = pd.DataFrame(
        [
            _blank_todd(
                event_edition_id=f"wsdc:{raw}:January 2018",
                wsdc_event_id=str(raw),
                event_series_id=str(canon),
                event_edition_name="Old id filing",
                start_date="2018-01-01",
            ),
            _blank_todd(
                event_edition_id=f"wsdc:{canon}:January 2018",
                wsdc_event_id=str(canon),
                event_series_id=str(canon),
                event_edition_name="Canonical filing",
                start_date="2018-01-19",
            ),
        ]
    )
    core = [
        {
            "event_id": canon,
            "event_year": 2018,
            "event_month": 1,
            "place_city": "Paris",
            "start_date": "2018-01-19",
        }
    ]
    tables = build_ee_tables(df, core_editions=core, decisions=DECISIONS)
    assert tables.gate["ok"] is True
    assert len(tables.attributes) == 1
    assert tables.attributes[0]["todd_edition_id"] == f"wsdc:{canon}:January 2018"
    assert tables.attributes[0]["match_kind"] == "exact"
    assert any(
        a.get("class") == "natural_key_collision_prefer_exact"
        for a in tables.gate.get("allowed_sample") or []
    )


def test_date_nat_and_value_mismatch_acknowledged():
    from transform.event_editions.build import _date

    assert _date(pd.NaT) is None
    assert _date("NaT") is None

    df = pd.DataFrame(
        [
            _blank_todd(
                event_edition_id="wsdc:31:November 2026",
                city="Wrong City",
                start_date="2026-11-01",
                end_date=pd.NaT,
            )
        ]
    )
    core = [
        {
            "event_id": 31,
            "event_year": 2026,
            "event_month": 11,
            "place_city": "South Lake Tahoe",
            "start_date": "2026-11-05",
        }
    ]
    tables = build_ee_tables(df, core_editions=core, decisions=DECISIONS)
    assert tables.gate["ok"] is True
    allowed_classes = {a["class"] for a in tables.gate.get("allowed_sample") or []}
    assert "value_city_mismatch" in allowed_classes
    assert "value_start_date_mismatch" in allowed_classes


def test_gate_dedupes_merge_map_missing():
    todd = [
        {
            "todd_edition_id": f"wsdc:99901:January 202{i}",
            "edition_status": "cancelled",
            "wsdc_event_id": 99901,
            "event_series_id": "42",
        }
        for i in range(4)
    ]
    matches = [
        {
            "todd_edition_id": r["todd_edition_id"],
            "event_id": 42,
            "event_year": 2020 + i,
            "event_month": 1,
            "match_kind": "unmatched",
            "canonical_event_id": 42,
            "raw_wsdc_event_id": 99901,
        }
        for i, r in enumerate(todd)
    ]
    # attach series on rows for gate
    for r in todd:
        r["event_series_id"] = "42"
    report = reconcile(
        todd_rows=todd,
        matches=matches,
        core_keys=set(),
        decisions=DECISIONS,
    )
    missing = [i for i in report["issues"] if i["class"] == "merge_map_missing"]
    assert len(missing) == 1

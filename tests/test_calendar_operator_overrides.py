"""Tests for curated calendar operator overrides."""

from __future__ import annotations

from transform.knowledge.calendar_operator_overrides import (
    CALENDAR_OPERATOR_OVERRIDES,
    SOUL_FLOW_PROVISIONAL_EVENT_ID,
    operator_override_upsert_rows,
)


def test_dmg_2026_hiatus_override_present():
    hits = [
        r
        for r in CALENDAR_OPERATOR_OVERRIDES
        if int(r["event_id"]) == 148
        and int(r["event_year"]) == 2026
        and r["calendar_status"] == "hiatus"
    ]
    assert len(hits) == 1
    assert hits[0]["planned_start_date"].isoformat() == "2026-07-24"


def test_soul_flow_2026_hiatus_and_2027_expected():
    hiatus = [
        r
        for r in CALENDAR_OPERATOR_OVERRIDES
        if int(r["event_id"]) == SOUL_FLOW_PROVISIONAL_EVENT_ID
        and int(r["event_year"]) == 2026
        and r["calendar_status"] == "hiatus"
    ]
    expected = [
        r
        for r in CALENDAR_OPERATOR_OVERRIDES
        if int(r["event_id"]) == SOUL_FLOW_PROVISIONAL_EVENT_ID
        and int(r["event_year"]) == 2027
        and r["calendar_status"] == "unconfirmed"
    ]
    assert len(hiatus) == 1
    assert hiatus[0]["planned_start_date"].isoformat() == "2026-12-11"
    assert len(expected) == 1
    assert expected[0]["planned_start_date"].isoformat() == "2027-12-10"
    assert SOUL_FLOW_PROVISIONAL_EVENT_ID != 342


def test_operator_override_upsert_payload():
    rows = operator_override_upsert_rows()
    dmg = next(r for r in rows if r["event_id"] == 148 and r["event_year"] == 2026)
    assert dmg["date_source"] == "operator"
    assert dmg["calendar_status"] == "hiatus"
    assert dmg["match_via"] == "operator_assumption"
    soul = next(
        r
        for r in rows
        if r["event_id"] == SOUL_FLOW_PROVISIONAL_EVENT_ID and r["event_year"] == 2026
    )
    assert soul["calendar_status"] == "hiatus"
    assert soul["date_source"] == "operator"

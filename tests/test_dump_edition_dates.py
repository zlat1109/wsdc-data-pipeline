"""Tests for dump competitionevents → edition day-date planning."""

from __future__ import annotations

from datetime import date

from transform.dump_edition_dates import (
    DATE_SOURCE_DUMP,
    DumpEditionRow,
    EditionDateRow,
    canonical_event_id,
    fill_rows_for_upsert,
    is_month_stub,
    plan_dump_edition_dates,
    summarize_plans,
)
from transform.knowledge.calendar_operator_overrides import SOUL_FLOW_PROVISIONAL_EVENT_ID


def test_is_month_stub_sentinel_and_nulls():
    assert is_month_stub(date(2020, 9, 1), date(2020, 9, 1))
    assert is_month_stub(None, None)
    assert is_month_stub(date(2020, 9, 1), None)
    assert not is_month_stub(date(2020, 9, 3), date(2020, 9, 6))
    assert not is_month_stub(date(2020, 9, 1), date(2020, 9, 3))


def test_canonical_merge_and_soul_flow():
    assert canonical_event_id(409) == 342
    assert canonical_event_id(342, "Global Grand Prix - West Coast Swing") == 342
    assert (
        canonical_event_id(342, "Soul Flow - West Coast Swing Festival (Hiatus -- 2026)")
        == SOUL_FLOW_PROVISIONAL_EVENT_ID
    )


def test_plan_fill_conflict_dump_stub_no_edition():
    dump = [
        DumpEditionRow(1, 255, "Indy Dance Explosion", date(2025, 6, 26), date(2025, 6, 29)),
        DumpEditionRow(2, 255, "Indy Dance Explosion", date(2024, 6, 1), date(2024, 6, 1)),
        DumpEditionRow(3, 255, "Indy Dance Explosion", date(2023, 6, 22), date(2023, 6, 25)),
        DumpEditionRow(4, 999001, "Ghost", date(2022, 1, 5), date(2022, 1, 8)),
        DumpEditionRow(5, 409, "GGP Paris", date(2026, 9, 18), date(2026, 9, 21)),
    ]
    editions = [
        EditionDateRow(255, 2025, 6, date(2025, 6, 1), date(2025, 6, 1), "Indy"),
        EditionDateRow(255, 2024, 6, date(2024, 6, 1), date(2024, 6, 1), "Indy"),
        EditionDateRow(255, 2023, 6, date(2023, 6, 22), date(2023, 6, 25), "Indy"),
        EditionDateRow(255, 2023, 6, date(2023, 6, 22), date(2023, 6, 25), "Indy"),  # dup key ok
        EditionDateRow(342, 2026, 9, date(2026, 9, 1), date(2026, 9, 1), "GGP"),
    ]
    # conflict case: ours day-precision differs
    editions.append(
        EditionDateRow(255, 2022, 7, date(2022, 7, 10), date(2022, 7, 12), "Indy")
    )
    dump.append(
        DumpEditionRow(6, 255, "Indy Dance Explosion", date(2022, 7, 14), date(2022, 7, 17))
    )

    plans = plan_dump_edition_dates(dump, editions)
    by_action = summarize_plans(plans)
    assert by_action["fill"] == 2  # 2025 stub + 409→342 stub
    assert by_action["dump_stub"] == 1
    assert by_action["match"] == 1
    assert by_action["no_edition"] == 1
    assert by_action["conflict"] == 1

    fills = fill_rows_for_upsert(plans)
    assert len(fills) == 2
    assert {r["event_id"] for r in fills} == {255, 342}
    assert all(r["date_source"] == DATE_SOURCE_DUMP for r in fills)
    paris = next(r for r in fills if r["event_id"] == 342)
    assert paris["planned_start_date"] == date(2026, 9, 18)
    assert paris["event_month"] == 9


def test_prefer_active_over_unconfirmed_and_skip_end_before_start():
    """Florida: Unconfirmed bot row must not win over Active final."""
    dump = [
        DumpEditionRow(
            3022,
            149,
            "Florida Dance Magic (Unconfirmed)",
            date(2025, 7, 25),
            date(2024, 7, 28),  # end before start
        ),
        DumpEditionRow(
            3273,
            149,
            "Florida Dance Magic",
            date(2025, 7, 24),
            date(2025, 7, 27),
        ),
        DumpEditionRow(
            3000,
            149,
            "Florida Dance Magic (Unconfirmed)",
            date(2025, 7, 20),
            date(2025, 7, 23),  # valid but older Unconfirmed
        ),
    ]
    editions = [
        EditionDateRow(149, 2025, 7, date(2025, 7, 24), date(2025, 7, 27), "FDM"),
    ]
    plans = plan_dump_edition_dates(dump, editions)
    by_ce = {p.dump_competitionevent_id: p.action for p in plans}
    assert by_ce[3022] == "skip_invalid"
    assert by_ce[3000] == "skip_duplicate"
    assert by_ce[3273] == "match"
    assert summarize_plans(plans).get("conflict", 0) == 0
    assert summarize_plans(plans).get("skip_duplicate", 0) == 1

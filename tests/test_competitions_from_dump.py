"""Tests for dump competitions → core.competitions planning."""

from datetime import date

from transform.competitions_from_dump import (
    DUMP_DIVISION_ID_TO_LEVEL,
    DumpCompetitionRow,
    EditionKeyRow,
    build_ce_to_edition_id,
    level_for_dump_division,
    plan_competition_rows,
    summarize_plans,
)
from transform.dump_edition_dates import DumpEditionRow


def test_dump_division_maps_to_canonical_levels():
    assert level_for_dump_division(8) == "All-Star"
    assert level_for_dump_division(7) == "Champion"
    assert level_for_dump_division(2) == "Master"
    assert set(DUMP_DIVISION_ID_TO_LEVEL) >= {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13}


def test_build_ce_to_edition_id_uses_series_and_month():
    dump_events = [
        DumpEditionRow(
            competitionevent_id=9001,
            series_event_id=300,
            event_name="Austin Rocks",
            start_date=date(2026, 9, 18),
            end_date=date(2026, 9, 20),
        )
    ]
    editions = [
        EditionKeyRow(
            edition_id=5149,
            event_id=300,
            event_year=2026,
            event_month=9,
            start_date=date(2026, 9, 18),
            end_date=date(2026, 9, 20),
            event_name="Austin Rocks",
        )
    ]
    assert build_ce_to_edition_id(dump_events, editions) == {9001: 5149}


def test_plan_marks_unmatched_and_skips_lindy():
    comps = [
        DumpCompetitionRow(
            competition_id=1,
            competitionevent_id=9001,
            dancetype_id=1,
            division_id=6,
            leader_count=10,
            follower_count=12,
            finals_count=5,
            created_at=None,
            updated_at=None,
        ),
        DumpCompetitionRow(
            competition_id=2,
            competitionevent_id=9002,
            dancetype_id=1,
            division_id=6,
            leader_count=8,
            follower_count=9,
            finals_count=4,
            created_at=None,
            updated_at=None,
        ),
        DumpCompetitionRow(
            competition_id=3,
            competitionevent_id=9001,
            dancetype_id=3,  # Lindy — skip
            division_id=6,
            leader_count=1,
            follower_count=1,
            finals_count=1,
            created_at=None,
            updated_at=None,
        ),
    ]
    planned = plan_competition_rows(comps, {9001: 5149})
    assert len(planned) == 2
    assert planned[0].match_status == "matched"
    assert planned[0].edition_id == 5149
    assert planned[0].level == "Advanced"
    assert planned[1].match_status == "unmatched"
    assert planned[1].edition_id is None
    summary = summarize_plans(planned)
    assert summary["matched"] == 1
    assert summary["unmatched"] == 1

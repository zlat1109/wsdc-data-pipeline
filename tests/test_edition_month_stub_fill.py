"""Tests for edition month-stub backfill and calendar upsert precedence."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "db"))

from edition_calendar import (  # noqa: E402
    fill_edition_month_stub_dates,
    should_apply_calendar_upsert,
)


class _FakeCursor:
    def __init__(self, rowcount: int = 3):
        self.statements: list[str] = []
        self.rowcount = rowcount

    def execute(self, sql: str, *_args):
        self.statements.append(sql)
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class _FakeConn:
    def __init__(self, cur: _FakeCursor):
        self._cur = cur

    def cursor(self):
        return self._cur


def test_fill_edition_month_stub_dates_runs_fill_sql():
    cur = _FakeCursor(rowcount=12)
    n = fill_edition_month_stub_dates(_FakeConn(cur))
    assert n == 12
    assert len(cur.statements) == 1
    sql = " ".join(cur.statements[0].split())
    assert "edition_date" in sql
    assert "start_date IS NULL OR ed.end_date IS NULL" in sql
    assert "'edition'" in sql


def test_upsert_dump_fills_month_stub_or_null():
    today = date(2026, 9, 24)
    assert should_apply_calendar_upsert(
        existing_source="wsdc_calendar",
        existing_start=date(2025, 6, 1),
        existing_end=date(2025, 6, 1),
        excluded_source="wsdc_dump",
        excluded_start=date(2025, 6, 26),
        excluded_end=date(2025, 6, 29),
        today=today,
    )
    assert should_apply_calendar_upsert(
        existing_source="operator",
        existing_start=None,
        existing_end=None,
        excluded_source="wsdc_dump",
        excluded_start=date(2025, 6, 26),
        excluded_end=date(2025, 6, 29),
        today=today,
    )


def test_upsert_dump_does_not_clobber_day_precision():
    today = date(2026, 9, 24)
    assert not should_apply_calendar_upsert(
        existing_source="wsdc_calendar",
        existing_start=date(2025, 6, 26),
        existing_end=date(2025, 6, 29),
        excluded_source="wsdc_dump",
        excluded_start=date(2025, 6, 20),
        excluded_end=date(2025, 6, 22),
        today=today,
    )


def test_upsert_calendar_blocked_by_month_stub_over_day_and_past_lock():
    today = date(2026, 9, 24)
    # Month stub must not overwrite day-precision.
    assert not should_apply_calendar_upsert(
        existing_source="wsdc_dump",
        existing_start=date(2025, 6, 26),
        existing_end=date(2025, 6, 29),
        excluded_source="wsdc_calendar",
        excluded_start=date(2025, 6, 1),
        excluded_end=date(2025, 6, 1),
        today=today,
    )
    # Past day-precision locked against calendar.
    assert not should_apply_calendar_upsert(
        existing_source="wsdc_dump",
        existing_start=date(2024, 3, 14),
        existing_end=date(2024, 3, 17),
        excluded_source="wsdc_calendar",
        excluded_start=date(2024, 3, 15),
        excluded_end=date(2024, 3, 18),
        today=today,
    )


def test_upsert_calendar_may_update_future_day_precision():
    today = date(2026, 9, 24)
    assert should_apply_calendar_upsert(
        existing_source="wsdc_dump",
        existing_start=date(2026, 11, 12),
        existing_end=date(2026, 11, 15),
        excluded_source="wsdc_calendar",
        excluded_start=date(2026, 11, 13),
        excluded_end=date(2026, 11, 16),
        today=today,
    )


def test_upsert_same_source_and_list_always_apply():
    today = date(2026, 9, 24)
    assert should_apply_calendar_upsert(
        existing_source="wsdc_events_list",
        existing_start=date(2026, 5, 1),
        existing_end=date(2026, 5, 3),
        excluded_source="operator",
        excluded_start=date(2026, 5, 2),
        excluded_end=date(2026, 5, 4),
        today=today,
    )
    assert should_apply_calendar_upsert(
        existing_source="operator",
        existing_start=date(2026, 5, 1),
        existing_end=date(2026, 5, 3),
        excluded_source="operator",
        excluded_start=date(2026, 5, 2),
        excluded_end=date(2026, 5, 4),
        today=today,
    )

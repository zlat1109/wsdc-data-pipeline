"""Tests for get_parse_in_flight probe / load detection."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_updates import get_parse_in_flight  # noqa: E402


class _Cursor:
    def __init__(self, responses):
        self._responses = list(responses)
        self.queries: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.queries.append(sql)

    def fetchone(self):
        if not self._responses:
            return None
        return self._responses.pop(0)


class _Conn:
    def __init__(self, responses):
        self._cursor = _Cursor(responses)

    def cursor(self):
        return self._cursor


def test_in_flight_detects_load_running_without_finished_at():
    started = datetime.now(timezone.utc) - timedelta(minutes=15)
    conn = _Conn([(99, started)])
    in_flight, run_id, age = get_parse_in_flight(conn, window_minutes=90)
    assert in_flight is True
    assert run_id == 99
    assert age is not None and age >= 14


def test_in_flight_detects_skipped_ready_probe_awaiting_success():
    started = datetime.now(timezone.utc) - timedelta(minutes=20)
    # First query (true load running) empty; second (ready probe) hits.
    conn = _Conn([None, (201, started)])
    in_flight, run_id, age = get_parse_in_flight(conn, window_minutes=90)
    assert in_flight is True
    assert run_id == 201
    assert age is not None and age >= 19
    second_sql = conn._cursor.queries[1].lower()
    assert "status in ('skipped', 'running')" in second_sql
    assert "parse_ready" in second_sql


def test_not_in_flight_when_no_rows():
    conn = _Conn([None, None])
    in_flight, run_id, age = get_parse_in_flight(conn, window_minutes=90)
    assert in_flight is False
    assert run_id is None
    assert age is None

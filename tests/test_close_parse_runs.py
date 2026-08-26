"""Tests for stuck parse_run close helpers."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from close_parse_runs import (  # noqa: E402
    close_stuck_running_parse_runs,
    find_stuck_running_parse_runs,
)


class _Cursor:
    def __init__(self, conn):
        self.conn = conn
        self._rows = []
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        sql_l = sql.lower()
        if "select run_id" in sql_l and "status = 'running'" in sql_l:
            cutoff = params[0]
            self._rows = [
                (r["run_id"], r["source"], "running", r["started_at"], None)
                for r in self.conn.rows
                if r["started_at"] < cutoff
            ]
        elif "update history.parse_runs" in sql_l:
            ids = set(params[1])
            n = 0
            for r in self.conn.rows:
                if r["run_id"] in ids:
                    r["status"] = "failed"
                    n += 1
            self.rowcount = n
            self._rows = []
        else:
            self._rows = []

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, rows):
        self.rows = rows

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        pass


def test_find_and_close_stuck_by_age():
    now = datetime.now(timezone.utc)
    rows = [
        {
            "run_id": 1,
            "source": "github-actions",
            "started_at": now - timedelta(minutes=120),
            "status": "running",
        },
        {
            "run_id": 2,
            "source": "github-actions",
            "started_at": now - timedelta(minutes=10),
            "status": "running",
        },
    ]
    conn = _Conn(rows)
    stuck = find_stuck_running_parse_runs(conn, min_age_minutes=90)
    assert len(stuck) == 1
    assert stuck[0]["run_id"] == 1
    summary = close_stuck_running_parse_runs(conn, min_age_minutes=90, dry_run=False)
    assert summary["closed_count"] == 1
    assert rows[0]["status"] == "failed"
    assert rows[1]["status"] == "running"

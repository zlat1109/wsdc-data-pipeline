"""Guards: weekly history SQL must handle same-day re-entry (PK valid_from)."""

from __future__ import annotations

from pathlib import Path

SQL_DIR = Path(__file__).resolve().parents[1] / "db" / "sql"


def test_points_roles_names_history_have_same_day_upsert():
    for name in (
        "record_weekly_points_history.sql",
        "record_weekly_roles_history.sql",
        "record_weekly_names_history.sql",
    ):
        text = (SQL_DIR / name).read_text(encoding="utf-8")
        assert "upd_same_day" in text, name
        assert "valid_from < c.change_date" in text, name
        assert "ON CONFLICT" in text, name

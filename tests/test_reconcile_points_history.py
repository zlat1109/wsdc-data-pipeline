"""Guards for points history reconcile (same-day PK / tombstone)."""

from __future__ import annotations

from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "reconcile_points_history.py"
)


def test_reconcile_points_history_tombstone_and_missing_use_on_conflict():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "ON CONFLICT (dancer_id, role, dance, level, valid_from)" in text
    assert text.count("ON CONFLICT (dancer_id, role, dance, level, valid_from)") >= 2
    assert "total_points = EXCLUDED.total_points" in text

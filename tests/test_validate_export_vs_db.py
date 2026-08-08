"""Tests for export-vs-db gate local health checks."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from validate_export_vs_db import _scheduled_events_health_problem  # noqa: E402


def test_scheduled_events_health_fails_on_missing(tmp_path):
    problem = _scheduled_events_health_problem(tmp_path)
    assert problem is not None
    assert "missing on disk" in problem


def test_scheduled_events_health_fails_on_header_only(tmp_path):
    (tmp_path / "scheduled_events.csv").write_text(
        "schedule_event_key,source_fingerprint,canonical_event_id,event_name\n",
        encoding="utf-8",
    )
    problem = _scheduled_events_health_problem(tmp_path)
    assert problem is not None
    assert "header-only" in problem


def test_scheduled_events_health_passes_with_rows(tmp_path):
    (tmp_path / "scheduled_events.csv").write_text(
        "schedule_event_key,source_fingerprint,canonical_event_id,event_name\n"
        "k1,fp1,101,Sample Event\n",
        encoding="utf-8",
    )
    assert _scheduled_events_health_problem(tmp_path) is None

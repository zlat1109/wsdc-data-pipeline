"""Tests for probe report builder (gate pending without live coverage)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from probe_report import build_probe_report
from wsdc_id_probe import ScanResult


def test_build_probe_report_uses_gate_pending_without_coverage():
    scan = ScanResult(
        watermark=28620,
        live_max_id=28620,
        new_ids=[],
        new_dancers=[],
    )
    report = build_probe_report(
        scan,
        coverage=None,
        ready=False,
        pending=["Big Apple Dance Festival", "Mediterranean Open WCS"],
        already_in_db=["SwingLab Berlin"],
        gate_status="pending",
        ready_reason="no_new_ids",
    )
    assert report.pending_events == [
        "Big Apple Dance Festival",
        "Mediterranean Open WCS",
    ]
    assert report.already_in_db_events == ["SwingLab Berlin"]
    assert report.gate_status == "pending"
    assert report.ready_reason == "no_new_ids"
    assert report.no_pending is False

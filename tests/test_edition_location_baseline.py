"""Tests for edition location baseline drift detection."""

from __future__ import annotations

import pandas as pd

from transform.geography.edition_location_baseline import find_csv_baseline_drifts
from transform.quality_audit import check_edition_location_baseline_drift


def test_find_csv_baseline_drifts_flags_mismatch():
    results = pd.DataFrame(
        [
            {"event_name_id": "324", "event_year": "2025", "event_month": "3", "location_id": "999", "event_name": "BTO Open"},
            {"event_name_id": "324", "event_year": "2025", "event_month": "3", "location_id": "999", "event_name": "BTO Open"},
        ]
    )
    baseline = pd.DataFrame(
        [
            {"event_id": "324", "event_year": "2025", "event_month": "3", "location_id": "148", "event_name": "BTO Open"},
        ]
    )
    drifts = find_csv_baseline_drifts(results, baseline)
    assert len(drifts) == 1
    assert drifts[0].baseline_location_id == "148"
    assert drifts[0].current_location_id == "999"


def test_find_csv_baseline_drifts_ignores_new_edition():
    results = pd.DataFrame(
        [
            {"event_name_id": "324", "event_year": "2026", "event_month": "9", "location_id": "148", "event_name": "Calgary Town Open"},
        ]
    )
    baseline = pd.DataFrame(
        [
            {"event_id": "324", "event_year": "2025", "event_month": "3", "location_id": "148", "event_name": "BTO Open"},
        ]
    )
    assert find_csv_baseline_drifts(results, baseline) == []


def test_find_csv_baseline_drifts_no_drift_when_match():
    results = pd.DataFrame(
        [
            {"event_name_id": "324", "event_year": "2025", "event_month": "3", "location_id": "148", "event_name": "BTO Open"},
        ]
    )
    baseline = pd.DataFrame(
        [
            {"event_id": "324", "event_year": "2025", "event_month": "3", "location_id": "148", "event_name": "BTO Open"},
        ]
    )
    assert find_csv_baseline_drifts(results, baseline) == []


def test_quality_audit_edition_location_baseline_drift():
    results = pd.DataFrame(
        [
            {"event_name_id": "324", "event_year": "2025", "event_month": "3", "location_id": "253", "event_name": "BTO Open"},
        ]
    )
    baseline = pd.DataFrame(
        [
            {"event_id": "324", "event_year": "2025", "event_month": "3", "location_id": "148", "event_name": "BTO Open"},
        ]
    )
    finding = check_edition_location_baseline_drift(results, baseline)
    assert finding is not None
    assert finding.code == "EDITION_LOCATION_BASELINE_DRIFT"
    assert finding.count == 1


def test_sync_edition_location_baseline_uses_fetchall_count():
    """auto_added must count RETURNING rows, not rely on rowcount."""
    from db.edition_location_baseline import sync_edition_location_baseline_after_load

    class FakeCursor:
        def __init__(self, rows):
            self._rows = rows

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql):
            pass

        def fetchall(self):
            return self._rows

    class FakeConn:
        def __init__(self):
            self._call = 0

        def cursor(self):
            self._call += 1
            if self._call == 1:
                return FakeCursor([])
            return FakeCursor([(1, 2026, 3, 148), (2, 2026, 4, 99)])

    report = sync_edition_location_baseline_after_load(FakeConn())
    assert report["auto_added"] == 2
    assert report["drift_count"] == 0


def test_edition_location_baseline_drift_sql_shape():
    from db.edition_location_baseline import DRIFT_SQL, AUTO_ADD_SQL

    assert "edition_location_baseline" in DRIFT_SQL
    assert "edition_location_baseline" in AUTO_ADD_SQL
    assert "ON CONFLICT" in AUTO_ADD_SQL

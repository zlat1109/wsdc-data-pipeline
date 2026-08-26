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


def test_baseline_override_conflict_flags_poison_seed():
    from transform.geography.edition_location_baseline import (
        find_baseline_override_conflicts,
    )
    from transform.quality_audit import check_baseline_vs_location_overrides

    baseline = pd.DataFrame(
        [
            {
                "event_id": "280",
                "event_year": "2026",
                "event_month": "7",
                "location_id": "253",
                "event_name": "Saint Petersburg WCS Nights",
            },
        ]
    )
    locations = pd.DataFrame(
        [
            {
                "location_id": "253",
                "event_country": "Australia",
                "event_location": "Perth, Australia",
                "event_location_standardized": "Perth, Australia",
            },
            {
                "location_id": "222",
                "event_country": "Russia",
                "event_location": "St. Petersburg, Russia",
                "event_location_standardized": "St. Petersburg, Russia",
            },
        ]
    )
    overrides = {"Saint Petersburg WCS Nights": "St. Petersburg, Russia"}
    conflicts = find_baseline_override_conflicts(
        baseline, locations, name_overrides=overrides
    )
    assert len(conflicts) == 1
    assert conflicts[0].baseline_location_id == "253"
    assert conflicts[0].override_location_id == "222"

    # No conflict when results==baseline but both wrong — drift silent; override check fires.
    finding = check_baseline_vs_location_overrides(baseline, locations)
    assert finding is not None
    assert finding.code == "BASELINE_VS_LOCATION_OVERRIDE"
    assert finding.count >= 1


def test_sync_edition_location_baseline_uses_fetchall_count():
    """auto_added must count RETURNING rows, not rely on rowcount."""
    from db.edition_location_baseline import sync_edition_location_baseline_after_load

    class FakeCursor:
        def __init__(self, rows):
            self._rows = rows
            self._sql = ""

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params=None):
            self._sql = sql

        def fetchall(self):
            return self._rows

        def fetchone(self):
            return self._rows[0] if self._rows else None

    class FakeConn:
        def __init__(self):
            self._call = 0

        def cursor(self):
            self._call += 1
            if self._call == 1:
                return FakeCursor([])  # drift
            if self._call == 2:
                return FakeCursor(
                    [
                        (1, 2026, 3, 148, "Event A"),
                        (2, 2026, 4, 99, "Event B"),
                    ]
                )  # auto-add
            # poison-seed country / resolve lookups — empty → no suspects
            return FakeCursor([])

    report = sync_edition_location_baseline_after_load(FakeConn())
    assert report["auto_added"] == 2
    assert report["drift_count"] == 0
    assert report["poison_seed_suspects"] == []


def test_find_poison_seed_auto_adds_flags_cross_country():
    from db.edition_location_baseline import find_poison_seed_auto_adds

    class FakeCursor:
        def __init__(self, conn):
            self.conn = conn
            self._rows = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params=None):
            sql_l = sql.lower()
            if "from core.locations" in sql_l and "location_id = any" in sql_l:
                # country lookup
                lids = list(params[0]) if params else []
                self._rows = [(lid, self.conn.countries.get(lid, "")) for lid in lids]
            elif "from core.locations" in sql_l:
                target = (params[0] if params else "").strip().lower()
                lid = self.conn.resolve.get(target)
                self._rows = [(lid,)] if lid else []
            else:
                self._rows = []

        def fetchall(self):
            return self._rows

        def fetchone(self):
            return self._rows[0] if self._rows else None

    class FakeConn:
        def __init__(self):
            self.countries = {253: "australia", 222: "russia"}
            self.resolve = {"st. petersburg, russia": 222}

        def cursor(self):
            return FakeCursor(self)

    auto_rows = [(280, 2026, 3, 253, "Saint Petersburg WCS Nights")]
    suspects = find_poison_seed_auto_adds(FakeConn(), auto_rows)
    assert len(suspects) == 1
    assert suspects[0]["location_id"] == 253
    assert suspects[0]["override_location_id"] == 222


def test_edition_location_baseline_drift_sql_shape():
    from db.edition_location_baseline import DRIFT_SQL, AUTO_ADD_SQL

    assert "edition_location_baseline" in DRIFT_SQL
    assert "edition_location_baseline" in AUTO_ADD_SQL
    assert "ON CONFLICT" in AUTO_ADD_SQL

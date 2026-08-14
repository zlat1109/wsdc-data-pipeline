"""Schedule tables must not FK core.locations (promote_core TRUNCATE CASCADE)."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "db"))

MIGRATIONS = PROJECT_ROOT / "db" / "migrations"
PROMOTE_CORE = PROJECT_ROOT / "db" / "sql" / "promote_core.sql"


def test_031_drops_schedule_location_fks():
    text = (MIGRATIONS / "031_schedule_location_no_fk.sql").read_text(encoding="utf-8")
    assert "DROP CONSTRAINT IF EXISTS events_list_current_location_id_fkey" in text
    assert "DROP CONSTRAINT IF EXISTS scheduled_events_location_id_fkey" in text
    assert "TRUNCATE CASCADE" in text or "CASCADE cannot wipe" in text


def test_later_migrations_do_not_readd_schedule_location_fk():
    for path in sorted(MIGRATIONS.glob("[0-9]*.sql")):
        if path.name <= "031_schedule_location_no_fk.sql":
            continue
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        if "events_list_current" in lowered or "scheduled_events" in lowered:
            assert "references core.locations" not in lowered, path.name


def test_promote_core_warns_against_schedule_location_fk():
    text = PROMOTE_CORE.read_text(encoding="utf-8")
    assert "TRUNCATE" in text
    assert "CASCADE" in text
    assert "events_list_current" in text
    assert "031" in text


def test_ensure_keeps_existing_snapshot(monkeypatch):
    class _Cur:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params=None):
            self._sql = sql

        def fetchone(self):
            if "events_list_current" in self._sql:
                return (12,)
            return (40,)

    class _Conn:
        def cursor(self):
            return _Cur()

    from refresh_events_list_current import ensure_events_list_after_load

    report = ensure_events_list_after_load(_Conn())
    assert report["action"] == "keep"
    assert report["current_before"] == 12


def test_ensure_rebuilds_current_from_archive(monkeypatch):
    calls = {"refresh": 0}

    class _Cur:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params=None):
            self._sql = sql
            self.description = (
                ("source_fingerprint",),
                ("event_name",),
                ("original_date",),
                ("start_date",),
                ("end_date",),
                ("results_year",),
                ("results_month",),
                ("location_raw",),
                ("country",),
                ("country_flag",),
                ("url",),
                ("status_event",),
                ("location_id",),
                ("location_source",),
                ("confirmed",),
                ("canceled",),
                ("on_hiatus",),
                ("is_active",),
            )

        def fetchone(self):
            if "INSERT INTO history.events_list_runs" in (self._sql or ""):
                return (9,)
            if "events_list_current" in (self._sql or ""):
                return (0,)
            if "scheduled_events" in (self._sql or "") and "SELECT count" in (
                self._sql or ""
            ):
                return (3,)
            return (0,)

        def fetchall(self):
            return [
                (
                    "fp1",
                    "SwingVester",
                    "",
                    "2026-12-30",
                    "2027-01-04",
                    2027,
                    1,
                    "Wels, Austria",
                    "Austria",
                    "AUT",
                    "https://www.swingvester.com/",
                    "Registry Event",
                    197,
                    "location_info",
                    True,
                    False,
                    False,
                    True,
                )
            ]

    class _Conn:
        def cursor(self):
            return _Cur()

    def fake_refresh(conn, events, run_id, catalog=None):
        calls["refresh"] += 1
        assert run_id == 9
        assert events[0]["event_name"] == "SwingVester"
        return 1

    monkeypatch.setattr(
        "refresh_events_list_current.refresh_events_list_current", fake_refresh
    )

    from refresh_events_list_current import ensure_events_list_after_load

    report = ensure_events_list_after_load(_Conn())
    assert report["action"] == "rebuild_from_archive"
    assert calls["refresh"] == 1
    assert report["current_after"] == 1


def test_ensure_restores_from_json_when_both_empty(tmp_path, monkeypatch):
    snapshot = tmp_path / "current.json"
    snapshot.write_text(
        '{"events": [{"source_fingerprint": "abc", "event_name": "X",'
        ' "is_active": true}]}',
        encoding="utf-8",
    )
    calls = {"restore": 0}

    class _Cur:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params=None):
            self._sql = sql

        def fetchone(self):
            return (0,)

    class _Conn:
        def cursor(self):
            return _Cur()

    def fake_restore(conn, events, source="full-parse-restore"):
        calls["restore"] += 1
        assert events[0]["event_name"] == "X"
        return {"run_id": 1, "current_count": 1, "upserted": 1}

    monkeypatch.setattr(
        "refresh_events_list_current.restore_events_list_from_snapshot",
        fake_restore,
    )

    from refresh_events_list_current import ensure_events_list_after_load

    report = ensure_events_list_after_load(_Conn(), snapshot_path=snapshot)
    assert report["action"] == "restored_from_json"
    assert calls["restore"] == 1

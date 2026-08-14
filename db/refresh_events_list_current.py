"""Rebuild core.events_list_current from the latest active schedule snapshot."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from transform.events_list_catalog import load_catalog
from transform.events_list_current import build_events_list_current
from transform.events_list_mapping import CatalogEvent

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CURRENT_SNAPSHOT = PROJECT_ROOT / "data" / "events_list" / "current.json"

_UPSERT_SCHEDULED_SQL = """
    INSERT INTO core.scheduled_events (
        source_fingerprint, event_name, original_date,
        start_date, end_date, results_year, results_month,
        location_raw, country, country_flag, url,
        status_event, location_id, location_source,
        confirmed, canceled, on_hiatus, is_active,
        first_seen_at, last_seen_at, last_run_id
    ) VALUES (
        %(source_fingerprint)s, %(event_name)s, %(original_date)s,
        %(start_date)s, %(end_date)s, %(results_year)s, %(results_month)s,
        %(location_raw)s, %(country)s, %(country_flag)s, %(url)s,
        %(status_event)s, %(location_id)s, %(location_source)s,
        %(confirmed)s, %(canceled)s, %(on_hiatus)s, %(is_active)s,
        %(now)s, %(now)s, %(run_id)s
    )
    ON CONFLICT (source_fingerprint) DO UPDATE SET
        event_name = EXCLUDED.event_name,
        original_date = EXCLUDED.original_date,
        start_date = EXCLUDED.start_date,
        end_date = EXCLUDED.end_date,
        results_year = EXCLUDED.results_year,
        results_month = EXCLUDED.results_month,
        location_raw = EXCLUDED.location_raw,
        country = EXCLUDED.country,
        country_flag = EXCLUDED.country_flag,
        url = EXCLUDED.url,
        status_event = EXCLUDED.status_event,
        location_id = COALESCE(
            core.scheduled_events.location_id, EXCLUDED.location_id
        ),
        location_source = CASE
            WHEN core.scheduled_events.location_id IS NULL
            THEN EXCLUDED.location_source
            ELSE core.scheduled_events.location_source
        END,
        confirmed = EXCLUDED.confirmed,
        canceled = EXCLUDED.canceled,
        on_hiatus = EXCLUDED.on_hiatus,
        is_active = EXCLUDED.is_active,
        last_seen_at = EXCLUDED.last_seen_at,
        last_run_id = EXCLUDED.last_run_id
"""

_INSERT_SQL = """
    INSERT INTO core.events_list_current (
        schedule_event_key, source_fingerprint, canonical_event_id,
        event_name, canonical_name, original_date,
        start_date, end_date, results_year, results_month,
        location_raw, country, country_flag, url,
        status_event, location_id, location_source,
        confirmed, canceled, on_hiatus,
        match_status, match_method, match_confidence,
        upcoming_editions, updated_at, last_run_id
    ) VALUES (
        %(schedule_event_key)s, %(source_fingerprint)s, %(canonical_event_id)s,
        %(event_name)s, %(canonical_name)s, %(original_date)s,
        %(start_date)s, %(end_date)s, %(results_year)s, %(results_month)s,
        %(location_raw)s, %(country)s, %(country_flag)s, %(url)s,
        %(status_event)s, %(location_id)s, %(location_source)s,
        %(confirmed)s, %(canceled)s, %(on_hiatus)s,
        %(match_status)s, %(match_method)s, %(match_confidence)s,
        %(upcoming_editions)s, %(now)s, %(run_id)s
    )
"""


def refresh_events_list_current(
    conn: Any,
    events: list[dict[str, Any]],
    run_id: int,
    *,
    catalog: list[CatalogEvent] | None = None,
) -> int:
    """Replace current-event snapshot; return row count."""
    if catalog is None:
        catalog = load_catalog()
    rows = build_events_list_current(events, catalog)
    now = datetime.now(timezone.utc)

    params = []
    for row in rows:
        params.append(
            {
                **row,
                "now": now,
                "run_id": run_id,
                "location_id": row.get("location_id") or None,
                "location_source": row.get("location_source") or None,
            }
        )

    with conn.cursor() as cur:
        cur.execute("TRUNCATE core.events_list_current")
        if params:
            cur.executemany(_INSERT_SQL, params)

    return len(rows)


def _schedule_counts(conn: Any) -> tuple[int, int]:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM core.events_list_current")
        current_n = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM core.scheduled_events")
        archive_n = cur.fetchone()[0]
    return int(current_n), int(archive_n)


def _coerce_location_id(value: Any, valid: set[int]) -> int | None:
    if value in (None, ""):
        return None
    try:
        lid = int(value)
    except (TypeError, ValueError):
        return None
    return lid if lid in valid else None


def _insert_restore_run(conn: Any, source: str, total: int) -> int:
    now = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO history.events_list_runs
                (scraped_at, source, total_events, added_count, removed_count, unchanged_count)
            VALUES (%s, %s, %s, 0, 0, %s)
            RETURNING run_id
            """,
            (now, source, total, total),
        )
        return int(cur.fetchone()[0])


def _active_archive_events(conn: Any) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT source_fingerprint, event_name, original_date,
                   start_date, end_date, results_year, results_month,
                   location_raw, country, country_flag, url, status_event,
                   location_id, location_source, confirmed, canceled, on_hiatus,
                   is_active
            FROM core.scheduled_events
            WHERE is_active = true
            """
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def restore_events_list_from_snapshot(
    conn: Any,
    events: list[dict[str, Any]],
    *,
    source: str = "full-parse-restore",
) -> dict[str, Any]:
    """Upsert snapshot rows into the archive and rebuild events_list_current."""
    catalog = load_catalog()
    with conn.cursor() as cur:
        cur.execute("SELECT location_id FROM core.locations")
        valid = {int(r[0]) for r in cur.fetchall()}

    cleaned: list[dict[str, Any]] = []
    for raw in events:
        ev = dict(raw)
        ev["location_id"] = _coerce_location_id(ev.get("location_id"), valid)
        if not ev.get("is_active", True):
            continue
        cleaned.append(ev)

    run_id = _insert_restore_run(conn, source, len(cleaned))
    now = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        for ev in cleaned:
            cur.execute(
                _UPSERT_SCHEDULED_SQL,
                {
                    "source_fingerprint": ev["source_fingerprint"],
                    "event_name": ev.get("event_name") or "",
                    "original_date": ev.get("original_date") or "",
                    "start_date": ev.get("start_date"),
                    "end_date": ev.get("end_date"),
                    "results_year": ev.get("results_year"),
                    "results_month": ev.get("results_month"),
                    "location_raw": ev.get("location_raw"),
                    "country": ev.get("country"),
                    "country_flag": ev.get("country_flag"),
                    "url": ev.get("url"),
                    "status_event": ev.get("status_event"),
                    "location_id": ev.get("location_id"),
                    "location_source": ev.get("location_source") or None,
                    "confirmed": ev.get("confirmed", True),
                    "canceled": ev.get("canceled", False),
                    "on_hiatus": ev.get("on_hiatus", False),
                    "is_active": True,
                    "now": now,
                    "run_id": run_id,
                },
            )
    current_count = refresh_events_list_current(
        conn, cleaned, run_id, catalog=catalog
    )
    return {"run_id": run_id, "current_count": current_count, "upserted": len(cleaned)}


def ensure_events_list_after_load(
    conn: Any,
    *,
    snapshot_path: Path | None = None,
) -> dict[str, Any]:
    """Keep the WSDC list snapshot after points promote.

    promote_core TRUNCATE CASCADE used to wipe schedule tables via location_id
    FKs (migration 030). Even after dropping those FKs, recover an empty
    snapshot from the archive or from ``data/events_list/current.json``.
    """
    current_n, archive_n = _schedule_counts(conn)
    report: dict[str, Any] = {
        "current_before": current_n,
        "archive_before": archive_n,
        "action": "keep",
    }
    if current_n > 0:
        return report

    if archive_n > 0:
        events = _active_archive_events(conn)
        run_id = _insert_restore_run(conn, "full-parse-rebuild-current", len(events))
        current_count = refresh_events_list_current(conn, events, run_id)
        report["action"] = "rebuild_from_archive"
        report["run_id"] = run_id
        report["current_after"] = current_count
        return report

    path = snapshot_path or CURRENT_SNAPSHOT
    if not path.exists():
        report["action"] = "empty_no_snapshot"
        return report
    doc = json.loads(path.read_text(encoding="utf-8"))
    events = doc.get("events") or []
    if not events:
        report["action"] = "empty_snapshot"
        return report
    restored = restore_events_list_from_snapshot(conn, events)
    current_after, archive_after = _schedule_counts(conn)
    report.update(restored)
    report["action"] = "restored_from_json"
    report["current_after"] = current_after
    report["archive_after"] = archive_after
    return report

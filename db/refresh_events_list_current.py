"""Rebuild core.events_list_current from the latest active schedule snapshot."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from transform.events_list_catalog import load_catalog
from transform.events_list_current import build_events_list_current
from transform.events_list_mapping import CatalogEvent

_INSERT_SQL = """
    INSERT INTO core.events_list_current (
        schedule_event_key, source_fingerprint, canonical_event_id,
        event_name, canonical_name, original_date,
        start_date, end_date, results_year, results_month,
        location_raw, country, country_flag, url,
        status_event, confirmed, canceled, on_hiatus,
        match_status, match_method, match_confidence,
        upcoming_editions, updated_at, last_run_id
    ) VALUES (
        %(schedule_event_key)s, %(source_fingerprint)s, %(canonical_event_id)s,
        %(event_name)s, %(canonical_name)s, %(original_date)s,
        %(start_date)s, %(end_date)s, %(results_year)s, %(results_month)s,
        %(location_raw)s, %(country)s, %(country_flag)s, %(url)s,
        %(status_event)s, %(confirmed)s, %(canceled)s, %(on_hiatus)s,
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

    params = [{**row, "now": now, "run_id": run_id} for row in rows]

    with conn.cursor() as cur:
        cur.execute("TRUNCATE core.events_list_current")
        if params:
            cur.executemany(_INSERT_SQL, params)

    return len(rows)

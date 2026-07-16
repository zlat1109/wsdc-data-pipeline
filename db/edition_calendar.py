"""Upsert WSDC calendar dates into core.edition_calendar_dates."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

_UPSERT_SQL = """
INSERT INTO core.edition_calendar_dates (
    event_id, event_year, event_month,
    planned_start_date, planned_end_date,
    calendar_status, date_source, source_fingerprint,
    calendar_title, url, match_via, scraped_at, updated_at
) VALUES (
    %(event_id)s, %(event_year)s, %(event_month)s,
    %(planned_start_date)s, %(planned_end_date)s,
    %(calendar_status)s, %(date_source)s, %(source_fingerprint)s,
    %(calendar_title)s, %(url)s, %(match_via)s, %(scraped_at)s, %(updated_at)s
)
ON CONFLICT (event_id, event_year, event_month) DO UPDATE SET
    planned_start_date = EXCLUDED.planned_start_date,
    planned_end_date = EXCLUDED.planned_end_date,
    calendar_status = EXCLUDED.calendar_status,
    date_source = EXCLUDED.date_source,
    source_fingerprint = EXCLUDED.source_fingerprint,
    calendar_title = EXCLUDED.calendar_title,
    url = EXCLUDED.url,
    match_via = EXCLUDED.match_via,
    scraped_at = EXCLUDED.scraped_at,
    updated_at = EXCLUDED.updated_at
WHERE core.edition_calendar_dates.date_source = 'wsdc_events_list'
   OR EXCLUDED.date_source = 'wsdc_calendar'
   OR core.edition_calendar_dates.date_source = EXCLUDED.date_source
"""

_ENRICH_EDITIONS_FROM_CALENDAR_SQL = """
UPDATE core.event_editions ed
SET
    start_date = CASE
        WHEN d.calendar_status IN ('hiatus', 'cancelled') THEN NULL
        ELSE d.planned_start_date
    END,
    end_date = CASE
        WHEN d.calendar_status IN ('hiatus', 'cancelled') THEN NULL
        ELSE d.planned_end_date
    END,
    date_source = d.date_source,
    calendar_status = d.calendar_status,
    event_occurred = CASE
        WHEN d.calendar_status IN ('hiatus', 'cancelled') THEN false
        ELSE true
    END
FROM core.edition_calendar_dates d
WHERE d.event_id = ed.event_id
  AND d.event_year = ed.event_year
  AND d.event_month = ed.event_month
"""

_ENRICH_EDITIONS_FROM_LIST_SQL = """
UPDATE core.event_editions ed
SET
    start_date = s.start_date,
    end_date = s.end_date,
    date_source = 'wsdc_events_list',
    calendar_status = CASE
        WHEN COALESCE(s.canceled, false) THEN 'cancelled'
        WHEN COALESCE(s.on_hiatus, false) THEN 'hiatus'
        WHEN COALESCE(s.confirmed, true) IS FALSE THEN 'unconfirmed'
        ELSE 'scheduled'
    END,
    event_occurred = CASE
        WHEN COALESCE(s.canceled, false) OR COALESCE(s.on_hiatus, false) THEN false
        ELSE true
    END
FROM core.events_list_current s
WHERE s.canonical_event_id = ed.event_id
  AND s.results_year = ed.event_year
  AND s.results_month = ed.event_month
  AND ed.start_date IS NULL
  AND s.start_date IS NOT NULL
  AND NOT COALESCE(s.canceled, false)
  AND NOT COALESCE(s.on_hiatus, false)
"""


def calendar_status_from_flags(flags: list[str] | None) -> str:
    flags = flags or []
    if "cancelled" in flags:
        return "cancelled"
    if "hiatus" in flags:
        return "hiatus"
    if "unconfirmed" in flags:
        return "unconfirmed"
    return "scheduled"


def rows_for_upsert(
    matched_rows: list[dict[str, Any]],
    *,
    scraped_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Build upsert payloads from match_calendar_to_editions output."""
    now = scraped_at or datetime.now(timezone.utc)
    out: list[dict[str, Any]] = []
    seen: set[tuple[int, int, int]] = set()

    for row in matched_rows:
        eid_raw = row.get("matched_event_id") or ""
        if not eid_raw:
            continue
        try:
            event_id = int(float(str(eid_raw)))
        except (TypeError, ValueError):
            continue

        status = calendar_status_from_flags(row.get("flags"))
        start = row.get("start_date") or None
        end = row.get("end_date") or None
        if not start:
            continue
        if not end:
            end = None

        # Prefer the edition ym when matched; else primary results ym.
        if row.get("match_status") == "matched" and row.get("matched_edition_id"):
            # Recover ym from candidates that exist on the row via results_year
            # when edition columns are not present — match stores edition id only.
            year = int(row.get("matched_event_year") or row.get("results_year"))
            month = int(row.get("matched_event_month") or row.get("results_month"))
        else:
            year = int(row["results_year"])
            month = int(row["results_month"])

        key = (event_id, year, month)
        if key in seen:
            continue
        seen.add(key)

        out.append(
            {
                "event_id": event_id,
                "event_year": year,
                "event_month": month,
                "planned_start_date": start,
                "planned_end_date": end,
                "calendar_status": status,
                "date_source": row.get("date_source") or "wsdc_calendar",
                "source_fingerprint": row.get("source_fingerprint"),
                "calendar_title": row.get("calendar_title") or row.get("event_name"),
                "url": row.get("url") or None,
                "match_via": row.get("match_via") or None,
                "scraped_at": now,
                "updated_at": now,
            }
        )
    return out


def upsert_edition_calendar_dates(conn: Any, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(_UPSERT_SQL, row)
        return len(rows)


def enrich_event_editions_dates(conn: Any) -> tuple[int, int]:
    """Copy durable calendar (+ list backfill) onto event_editions. Returns (cal, list)."""
    with conn.cursor() as cur:
        cur.execute(_ENRICH_EDITIONS_FROM_CALENDAR_SQL)
        from_cal = cur.rowcount
        cur.execute(_ENRICH_EDITIONS_FROM_LIST_SQL)
        from_list = cur.rowcount
    return from_cal, from_list

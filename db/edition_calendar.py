"""Upsert WSDC calendar dates into core.edition_calendar_dates."""

from __future__ import annotations

from datetime import date, datetime, timezone
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


def remap_stale_calendar_event_ids(conn: Any) -> int:
    """Move durable calendar rows onto current edition event_ids when titles match.

    Returns number of source rows remapped or dropped after merge.
    """
    import pandas as pd

    from transform.events_calendar_remap import plan_calendar_event_id_remaps

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                event_id::text,
                event_year::text,
                event_month::text,
                calendar_title
            FROM core.edition_calendar_dates
            """
        )
        calendar = pd.DataFrame(
            cur.fetchall(),
            columns=["event_id", "event_year", "event_month", "calendar_title"],
        )
        cur.execute(
            """
            SELECT
                ed.event_id::text,
                c.canonical_name AS event_name,
                ed.event_year::text,
                ed.event_month::text
            FROM core.event_editions ed
            JOIN core.event_catalog c ON c.event_id = ed.event_id
            """
        )
        editions = pd.DataFrame(
            cur.fetchall(),
            columns=["event_id", "event_name", "event_year", "event_month"],
        )

    remaps = plan_calendar_event_id_remaps(calendar, editions)
    if not remaps:
        return 0

    moved = 0
    with conn.cursor() as cur:
        for remap in remaps:
            old_id = int(remap["old_event_id"])
            new_id = int(remap["new_event_id"])
            year = int(remap["event_year"])
            month = int(remap["event_month"])
            cur.execute(
                """
                SELECT 1
                FROM core.edition_calendar_dates
                WHERE event_id = %s AND event_year = %s AND event_month = %s
                """,
                (new_id, year, month),
            )
            target_exists = cur.fetchone() is not None
            if target_exists:
                cur.execute(
                    """
                    DELETE FROM core.edition_calendar_dates
                    WHERE event_id = %s AND event_year = %s AND event_month = %s
                    """,
                    (old_id, year, month),
                )
            else:
                cur.execute(
                    """
                    UPDATE core.edition_calendar_dates
                    SET
                        event_id = %s,
                        match_via = CASE
                            WHEN match_via IS NULL OR match_via = '' THEN 'remap_stale_event_id'
                            WHEN match_via LIKE '%%remap_stale_event_id%%' THEN match_via
                            ELSE match_via || '+remap_stale_event_id'
                        END,
                        updated_at = now()
                    WHERE event_id = %s AND event_year = %s AND event_month = %s
                    """,
                    (new_id, old_id, year, month),
                )
            moved += cur.rowcount
    return moved


def enrich_event_editions_dates(conn: Any) -> tuple[int, int]:
    """Copy durable calendar (+ list backfill) onto event_editions. Returns (cal, list)."""
    remap_stale_calendar_event_ids(conn)
    with conn.cursor() as cur:
        cur.execute(_ENRICH_EDITIONS_FROM_CALENDAR_SQL)
        from_cal = cur.rowcount
        cur.execute(_ENRICH_EDITIONS_FROM_LIST_SQL)
        from_list = cur.rowcount
    return from_cal, from_list


def durable_date_count(conn: Any) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM core.edition_calendar_dates")
        return int(cur.fetchone()[0])


def ensure_edition_calendar_after_load(
    conn: Any,
    *,
    artifact_path: Any | None = None,
) -> dict[str, Any]:
    """If durable calendar archive is empty, rebuild from scrape or artifact.

    promote_core used to CASCADE-wipe this table via FK to core.events; even after
    dropping the FK, recover if the archive is empty so export still has day dates.
    """
    from datetime import datetime, timezone
    from pathlib import Path

    import pandas as pd

    from parser.events_calendar_scraper import scrape_events_calendar
    from transform.events_calendar_match import match_calendar_to_editions
    from transform.events_calendar_normalize import normalize_calendar_events

    report: dict[str, Any] = {"durable_before": durable_date_count(conn), "action": "noop"}
    if report["durable_before"] > 0:
        enrich_event_editions_dates(conn)
        report["action"] = "enrich_only"
        report["durable_after"] = report["durable_before"]
        return report

    def _frames() -> tuple[Any, Any]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    ed.edition_id::text, ed.event_id::text, c.canonical_name,
                    ed.event_year::text, ed.event_month::text
                FROM core.event_editions ed
                JOIN core.event_catalog c ON c.event_id = ed.event_id
                """
            )
            editions = pd.DataFrame(
                cur.fetchall(),
                columns=["edition_id", "event_id", "event_name", "event_year", "event_month"],
            )
            cur.execute(
                "SELECT event_id::text, canonical_name, url FROM core.event_catalog"
            )
            catalog = pd.DataFrame(
                cur.fetchall(), columns=["event_id", "canonical_name", "url"]
            )
        return editions, catalog

    def _upsert_from_events(events: list[dict[str, Any]], action: str) -> dict[str, Any]:
        editions, catalog = _frames()
        if editions.empty:
            report["action"] = "failed_no_editions"
            report["durable_after"] = 0
            return report
        matched, _summary = match_calendar_to_editions(events, editions, catalog)
        rows = rows_for_upsert(
            [r for r in matched if r.get("matched_event_id")],
            scraped_at=datetime.now(timezone.utc),
        )
        upserted = upsert_edition_calendar_dates(conn, rows)
        enrich_event_editions_dates(conn)
        report["action"] = action
        report["upserted"] = upserted
        report["durable_after"] = durable_date_count(conn)
        return report

    try:
        raw = scrape_events_calendar()
        events = normalize_calendar_events(raw, min_start=date(2025, 1, 1))
        return _upsert_from_events(events, "scrape_upsert")
    except Exception as scrape_exc:
        report["scrape_error"] = str(scrape_exc)

    path = Path(artifact_path) if artifact_path else None
    if path is None:
        root = Path(__file__).resolve().parents[1]
        path = root / "data" / "events_calendar" / "current.json"
    if not path.exists():
        report["action"] = "failed_empty"
        report["durable_after"] = 0
        return report

    import json

    doc = json.loads(path.read_text(encoding="utf-8"))
    events = doc.get("events") or []
    report["artifact"] = str(path)
    return _upsert_from_events(events, "artifact_upsert")

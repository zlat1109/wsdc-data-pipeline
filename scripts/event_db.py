"""Check whether a WSDC event edition is already loaded in core.results."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from parser.event_name_matcher import find_best_match

ISO_DATE = "%Y-%m-%d"


def _parse_iso_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], ISO_DATE).date()
    except ValueError:
        return None


def event_results_edition(event: dict[str, Any]) -> tuple[int | None, int | None]:
    """WSDC results edition year/month from snapshot row (explicit or start_date)."""
    year = event.get("results_year")
    month = event.get("results_month")
    if year is not None and month is not None:
        try:
            return int(year), int(month)
        except (TypeError, ValueError):
            pass
    start = _parse_iso_date(event.get("start_date"))
    if start is not None:
        return start.year, start.month
    return None, None


def event_has_concluded(event: dict[str, Any], today: date | None = None) -> bool:
    """True when the event weekend is over (results may exist on WSDC)."""
    today = today or date.today()
    end = _parse_iso_date(event.get("end_date"))
    start = _parse_iso_date(event.get("start_date"))
    last_day = end or start
    if last_day is None:
        return True
    return last_day < today


def fetch_event_names_for_edition(conn, year: int, month: int) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT e.name
            FROM core.results r
            JOIN core.events e ON e.event_id = r.event_id
            WHERE r.event_year = %s AND r.event_month = %s
            """,
            (year, month),
        )
        return [row[0] for row in cur.fetchall() if row[0]]


def event_edition_in_db(
    conn,
    event_name: str,
    year: int | None,
    month: int | None,
    *,
    threshold: float = 0.75,
) -> bool:
    if year is None or month is None:
        return False
    db_names = fetch_event_names_for_edition(conn, year, month)
    if not db_names:
        return False
    match, _ = find_best_match(event_name, db_names, threshold=threshold)
    return match is not None


def split_pending_events(
    conn,
    events: list[dict[str, Any]],
    *,
    threshold: float = 0.75,
    today: date | None = None,
) -> tuple[list[str], list[str]]:
    """Return (pending_names, already_in_db_names) for concluded snapshot events."""
    today = today or date.today()
    pending: list[str] = []
    already: list[str] = []
    for event in events:
        name = (event.get("name") or "").strip()
        if not name:
            continue
        if not event_has_concluded(event, today):
            continue
        year, month = event_results_edition(event)
        if event_edition_in_db(conn, name, year, month, threshold=threshold):
            already.append(name)
        else:
            pending.append(name)
    return pending, already

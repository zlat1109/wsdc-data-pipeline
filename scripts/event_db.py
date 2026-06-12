"""Check whether a WSDC event edition is already loaded in core.results."""

from __future__ import annotations

from typing import Any

from parser.event_name_matcher import find_best_match


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
) -> tuple[list[str], list[str]]:
    """Return (pending_names, already_in_db_names) for snapshot events."""
    pending: list[str] = []
    already: list[str] = []
    for event in events:
        name = (event.get("name") or "").strip()
        if not name:
            continue
        year = event.get("results_year")
        month = event.get("results_month")
        if event_edition_in_db(conn, name, year, month, threshold=threshold):
            already.append(name)
        else:
            pending.append(name)
    return pending, already

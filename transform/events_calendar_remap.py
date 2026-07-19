"""Remap durable calendar dates when catalog event_ids were reassigned.

``core.edition_calendar_dates`` is keyed by ``(event_id, year, month)`` and survives
points rebuilds. When an event is re-catalogued under a new ``event_id``, enrich
joins miss and editions stay without ``start_date`` (e.g. SwingLab Berlin).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from transform.events_calendar_normalize import name_key


def plan_calendar_event_id_remaps(
    calendar_rows: list[dict[str, Any]] | pd.DataFrame,
    editions: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Return remaps where calendar title+ym uniquely matches a current edition.

    Each item: old_event_id, new_event_id, event_year, event_month, calendar_title.
    """
    if editions is None or editions.empty:
        return []

    ed = editions.copy()
    ed["event_id"] = ed["event_id"].astype(str)
    ed["event_year"] = ed["event_year"].astype(int)
    ed["event_month"] = ed["event_month"].astype(int)
    ed["name_key"] = ed["event_name"].map(lambda n: name_key(str(n or "")))

    by_name_ym: dict[tuple[str, int, int], set[str]] = {}
    for _, row in ed.iterrows():
        nk = str(row["name_key"] or "")
        if not nk:
            continue
        key = (nk, int(row["event_year"]), int(row["event_month"]))
        by_name_ym.setdefault(key, set()).add(str(row["event_id"]))

    if isinstance(calendar_rows, pd.DataFrame):
        rows = calendar_rows.to_dict(orient="records")
    else:
        rows = list(calendar_rows or [])

    remaps: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()
    for row in rows:
        old_id = str(row.get("event_id") or "").strip()
        if not old_id:
            continue
        try:
            year = int(row.get("event_year"))
            month = int(row.get("event_month"))
        except (TypeError, ValueError):
            continue
        title = str(row.get("calendar_title") or row.get("event_name") or "").strip()
        nk = name_key(title)
        if not nk:
            continue
        candidates = by_name_ym.get((nk, year, month)) or set()
        if len(candidates) != 1:
            continue
        new_id = next(iter(candidates))
        if new_id == old_id:
            continue
        dedupe = (old_id, year, month)
        if dedupe in seen:
            continue
        seen.add(dedupe)
        remaps.append(
            {
                "old_event_id": old_id,
                "new_event_id": new_id,
                "event_year": year,
                "event_month": month,
                "calendar_title": title,
            }
        )
    return remaps

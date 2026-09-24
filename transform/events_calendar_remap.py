"""Remap durable calendar dates when catalog event_ids were reassigned.

``core.edition_calendar_dates`` is keyed by ``(event_id, year, month)`` and survives
points rebuilds. When an event is re-catalogued under a new ``event_id``, enrich
joins miss and editions stay without ``start_date`` (e.g. SwingLab Berlin).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from transform.events_calendar_normalize import name_key
from transform.knowledge.event_aliases import MERGE_EVENT_ID_MAP


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


def plan_merge_map_calendar_remaps(
    calendar_rows: list[dict[str, Any]] | pd.DataFrame,
    *,
    merge_map: dict[int, int] | None = None,
) -> list[dict[str, Any]]:
    """Remap calendar rows whose event_id is a MERGE_EVENT_ID_MAP ghost.

    Title matching cannot collapse Paris Swing Classic (307/543) → Paris Westie
    Fest (272) when the calendar title and catalog name differ; apply the merge
    map directly so durable dates stop orphaning against event_catalog.
    """
    mapping = merge_map if merge_map is not None else MERGE_EVENT_ID_MAP
    if not mapping:
        return []

    if isinstance(calendar_rows, pd.DataFrame):
        rows = calendar_rows.to_dict(orient="records")
    else:
        rows = list(calendar_rows or [])

    remaps: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()
    for row in rows:
        raw_id = str(row.get("event_id") or "").strip()
        if not raw_id or not raw_id.isdigit():
            continue
        old_id = int(raw_id)
        new_id = mapping.get(old_id)
        if new_id is None or int(new_id) == old_id:
            continue
        try:
            year = int(row.get("event_year"))
            month = int(row.get("event_month"))
        except (TypeError, ValueError):
            continue
        dedupe = (str(old_id), year, month)
        if dedupe in seen:
            continue
        seen.add(dedupe)
        title = str(row.get("calendar_title") or row.get("event_name") or "").strip()
        remaps.append(
            {
                "old_event_id": str(old_id),
                "new_event_id": str(int(new_id)),
                "event_year": year,
                "event_month": month,
                "calendar_title": title,
            }
        )
    return remaps


def plan_mismatched_title_calendar_deletes(
    calendar_rows: list[dict[str, Any]] | pd.DataFrame,
) -> list[dict[str, Any]]:
    """Drop durable URL-matched rows whose listing title is a different brand.

    Only ``match_via`` of ``url`` / ``url_host`` (shared marketing sites) are
    purged — name-based near-matches like ``NeverlandSwing`` stay for the year
    calendar filter. Typical case: Soul Flow hiatus listed under the old Global
    Grand Prix URL and stuck on event_id 342.
    """
    from transform.events_calendar_normalize import calendar_title_matches_event

    if isinstance(calendar_rows, pd.DataFrame):
        rows = calendar_rows.to_dict(orient="records")
    else:
        rows = list(calendar_rows or [])

    deletes: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()
    for row in rows:
        raw_id = str(row.get("event_id") or "").strip()
        if not raw_id:
            continue
        via = str(row.get("match_via") or "").lower()
        # Remap suffixes like "url+remap_stale_event_id" still count as URL pins.
        if "url" not in via:
            continue
        event_name = str(row.get("event_name") or "").strip()
        title = str(row.get("calendar_title") or "").strip()
        if not event_name or not title or event_name.lower() == "nan":
            continue
        if calendar_title_matches_event(event_name, title):
            continue
        try:
            year = int(row.get("event_year"))
            month = int(row.get("event_month"))
        except (TypeError, ValueError):
            continue
        dedupe = (raw_id, year, month)
        if dedupe in seen:
            continue
        seen.add(dedupe)
        deletes.append(
            {
                "event_id": raw_id,
                "event_year": year,
                "event_month": month,
                "calendar_title": title,
                "event_name": event_name,
            }
        )
    return deletes

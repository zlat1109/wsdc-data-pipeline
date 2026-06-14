"""Collapse active schedule editions to one row per logical WSDC event."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from transform.events_list_mapping import (
    CatalogEvent,
    MappingResult,
    build_url_index,
    map_scheduled_event,
)
from transform.events_list_normalize import normalize_url

_CONFIRMED_MATCH_STATUSES = frozenset({"confirmed"})


def schedule_event_key(row: dict[str, Any], mapping: MappingResult) -> str:
    """Stable identity for a registry/trial brand on the schedule."""
    if (
        mapping.canonical_event_id is not None
        and mapping.match_status in _CONFIRMED_MATCH_STATUSES
    ):
        return f"evt:{mapping.canonical_event_id}"
    url_norm = normalize_url(row.get("url") or "")
    if url_norm:
        return f"url:{url_norm}"
    return f"fp:{row['source_fingerprint']}"


def build_events_list_current(
    events: list[dict[str, Any]],
    catalog: list[CatalogEvent],
) -> list[dict[str, Any]]:
    """One row per logical event; nearest upcoming edition wins."""
    active = [e for e in events if e.get("is_active", True)]
    if not active:
        return []

    url_index = build_url_index(catalog)
    name_list = sorted({ev.name for ev in catalog})

    grouped: dict[str, list[tuple[dict[str, Any], MappingResult]]] = defaultdict(list)
    for row in active:
        mapping = map_scheduled_event(row, catalog, url_index, name_list)
        key = schedule_event_key(row, mapping)
        grouped[key].append((row, mapping))

    current: list[dict[str, Any]] = []
    for key, items in grouped.items():
        row, mapping = min(items, key=lambda pair: pair[0].get("start_date") or "9999-12-31")
        current.append(
            _current_row(
                key,
                row,
                mapping,
                upcoming_editions=len(items),
            )
        )

    current.sort(key=lambda r: (r.get("start_date") or "", r.get("event_name") or ""))
    return current


def _current_row(
    key: str,
    row: dict[str, Any],
    mapping: MappingResult,
    *,
    upcoming_editions: int,
) -> dict[str, Any]:
    return {
        "schedule_event_key": key,
        "source_fingerprint": row["source_fingerprint"],
        "canonical_event_id": mapping.canonical_event_id,
        "event_name": row.get("event_name") or "",
        "canonical_name": mapping.canonical_name,
        "original_date": row.get("original_date") or "",
        "start_date": row.get("start_date"),
        "end_date": row.get("end_date"),
        "results_year": row.get("results_year"),
        "results_month": row.get("results_month"),
        "location_raw": row.get("location_raw") or "",
        "country": row.get("country") or "",
        "country_flag": row.get("country_flag") or "",
        "url": row.get("url") or "",
        "status_event": row.get("status_event") or "",
        "confirmed": bool(row.get("confirmed", True)),
        "canceled": bool(row.get("canceled")),
        "on_hiatus": bool(row.get("on_hiatus")),
        "match_status": mapping.match_status,
        "match_method": mapping.match_method,
        "match_confidence": mapping.confidence,
        "upcoming_editions": upcoming_editions,
    }

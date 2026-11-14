"""Match Todd WSDC editions onto ``core.event_editions`` natural keys."""

from __future__ import annotations

from typing import Any, Iterable

from transform.event_editions.keys import month_shift, parse_todd_edition_id
from transform.knowledge.event_aliases import MERGE_EVENT_ID_MAP


def canonical_event_id(wsdc_event_id: int) -> int:
    return int(MERGE_EVENT_ID_MAP.get(int(wsdc_event_id), int(wsdc_event_id)))


def build_core_key_set(
    editions: Iterable[dict[str, Any]],
) -> set[tuple[int, int, int]]:
    out: set[tuple[int, int, int]] = set()
    for row in editions:
        out.add((int(row["event_id"]), int(row["event_year"]), int(row["event_month"])))
    return out


def match_edition(
    todd_edition_id: str,
    *,
    core_keys: set[tuple[int, int, int]],
) -> dict[str, Any] | None:
    """Return match info for a Todd id, or None if non-WSDC."""
    parsed = parse_todd_edition_id(todd_edition_id)
    if parsed is None:
        return None
    eid, y, m = parsed.wsdc_event_id, parsed.event_year, parsed.event_month
    can = canonical_event_id(eid)

    if (eid, y, m) in core_keys:
        return {
            "todd_edition_id": parsed.todd_edition_id,
            "event_id": eid,
            "event_year": y,
            "event_month": m,
            "match_kind": "exact",
            "canonical_event_id": can,
        }
    if can != eid and (can, y, m) in core_keys:
        return {
            "todd_edition_id": parsed.todd_edition_id,
            "event_id": can,
            "event_year": y,
            "event_month": m,
            "match_kind": "merge_map",
            "canonical_event_id": can,
            "raw_wsdc_event_id": eid,
        }
    for delta in (-1, 1):
        yy, mm = month_shift(y, m, delta)
        for candidate in (eid, can):
            if (candidate, yy, mm) in core_keys:
                return {
                    "todd_edition_id": parsed.todd_edition_id,
                    "event_id": candidate,
                    "event_year": yy,
                    "event_month": mm,
                    "match_kind": "month_shift",
                    "canonical_event_id": can,
                    "raw_wsdc_event_id": eid,
                    "filing_year": y,
                    "filing_month": m,
                }
    return {
        "todd_edition_id": parsed.todd_edition_id,
        "event_id": can,
        "event_year": y,
        "event_month": m,
        "match_kind": "unmatched",
        "canonical_event_id": can,
        "raw_wsdc_event_id": eid,
    }

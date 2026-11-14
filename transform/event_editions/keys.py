"""Parse Todd ``event_edition_id`` keys (``wsdc:<id>:<Month YYYY>``)."""

from __future__ import annotations

from datetime import datetime
from typing import NamedTuple


class ToddEditionKey(NamedTuple):
    todd_edition_id: str
    wsdc_event_id: int
    event_year: int
    event_month: int


def parse_todd_edition_id(todd_id: str) -> ToddEditionKey | None:
    """Return key parts for a WSDC Todd id, or None if non-WSDC / malformed."""
    if not todd_id or not str(todd_id).startswith("wsdc:"):
        return None
    parts = str(todd_id).split(":", 2)
    if len(parts) != 3:
        return None
    try:
        eid = int(parts[1])
        dt = datetime.strptime(parts[2], "%B %Y")
    except (TypeError, ValueError):
        return None
    return ToddEditionKey(
        todd_edition_id=str(todd_id),
        wsdc_event_id=eid,
        event_year=dt.year,
        event_month=dt.month,
    )


def month_shift(year: int, month: int, delta: int) -> tuple[int, int]:
    m = month + delta
    y = year
    if m == 0:
        return y - 1, 12
    if m == 13:
        return y + 1, 1
    return y, m

"""Match Competition Results editions to ``core.event_editions``."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from transform.dump_edition_dates import canonical_event_id

_MONTH_NAME = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

_EDITION_RE = re.compile(
    r"^wsdc:(\d+):([A-Za-z]+) (\d+)$"
)


@dataclass(frozen=True)
class EditionKey:
    edition_id: int
    event_id: int
    event_year: int
    event_month: int


@dataclass(frozen=True)
class CrEditionMatch:
    cr_edition_id: str
    wsdc_event_id: int | None
    cr_name: str
    filing_year: int | None
    filing_month: int | None
    canonical_event_id: int | None
    edition_id: int | None
    match_status: str  # matched | unmatched
    scoring_source: str


def parse_cr_edition_id(cr_edition_id: str) -> tuple[int | None, int | None, int | None]:
    """Return (raw_wsdc_event_id, filing_month, filing_year) from ``wsdc:id:Month YYYY``."""
    m = _EDITION_RE.match(str(cr_edition_id or "").strip())
    if not m:
        return None, None, None
    raw_id = int(m.group(1))
    mon = _MONTH_NAME.get(m.group(2).lower())
    year = int(m.group(3))
    return raw_id, mon, year


def edition_lookup(
    editions: Sequence[EditionKey] | Iterable[Mapping[str, Any]],
) -> dict[tuple[int, int, int], int]:
    """Map (event_id, year, month) → edition_id."""
    out: dict[tuple[int, int, int], int] = {}
    for raw in editions:
        if isinstance(raw, EditionKey):
            key = (raw.event_id, raw.event_year, raw.event_month)
            out[key] = raw.edition_id
        else:
            key = (
                int(raw["event_id"]),
                int(raw["event_year"]),
                int(raw["event_month"]),
            )
            out[key] = int(raw["edition_id"])
    return out


def match_cr_edition(
    *,
    cr_edition_id: str,
    cr_name: str = "",
    wsdc_event_id: Any = None,
    scoring_source: str = "",
    lookup: Mapping[tuple[int, int, int], int],
) -> CrEditionMatch:
    raw_from_id, filing_month, filing_year = parse_cr_edition_id(cr_edition_id)
    raw_id: int | None
    try:
        raw_id = int(wsdc_event_id) if wsdc_event_id not in (None, "") else raw_from_id
    except (TypeError, ValueError):
        raw_id = raw_from_id

    canon: int | None = None
    edition_id: int | None = None
    status = "unmatched"
    if raw_id is not None and filing_year is not None and filing_month is not None:
        canon = canonical_event_id(raw_id, cr_name or "")
        edition_id = lookup.get((canon, filing_year, filing_month))
        if edition_id is not None:
            status = "matched"

    src = (scoring_source or "").strip().lower()
    return CrEditionMatch(
        cr_edition_id=cr_edition_id,
        wsdc_event_id=raw_id,
        cr_name=cr_name or "",
        filing_year=filing_year,
        filing_month=filing_month,
        canonical_event_id=canon,
        edition_id=edition_id,
        match_status=status,
        scoring_source=src,
    )

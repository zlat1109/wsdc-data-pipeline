"""Detect event-name vs location-country collisions (shared wrong location_id).

Classic failure: Sweden Westie Gala rows tagged with Wailea / Aloha Open (USA).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

# High-signal tokens in event_name that imply a country.
# Keep conservative — false positives are worse than misses for CI guards.
NAME_COUNTRY_HINTS: list[tuple[str, str]] = [
    (r"\bsweden\b|\bswedish\b", "Sweden"),
    (r"\bfrench\b|\bfrance\b|\bpink city\b", "France"),
    (r"\btoronto\b", "Canada"),
    (r"\bsofia\b|\bbulgaria\b", "Bulgaria"),
    (r"\btrinity\b", "Ireland"),
    (r"\bnortheast swing classic\b", "United States"),
    # Baltic Swing is in Gdańsk, Poland (not Phoenix / not Latvia-by-name).
    (r"\bbaltic swing\b", "Poland"),
]


@dataclass(frozen=True)
class NameLocationConflict:
    event_name: str
    location_id: str
    location_country: str
    name_hints: tuple[str, ...]
    row_count: int


def _norm(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def hint_countries_from_event_name(event_name: str) -> list[str]:
    name = event_name.lower()
    return [country for pat, country in NAME_COUNTRY_HINTS if re.search(pat, name)]


def find_name_location_country_conflicts(
    results_df: pd.DataFrame,
    location_df: pd.DataFrame,
) -> list[NameLocationConflict]:
    """Return event×location pairs where name hints disagree with location country."""
    if results_df is None or results_df.empty:
        return []
    if location_df is None or location_df.empty:
        return []
    if "event_name" not in results_df.columns or "location_id" not in results_df.columns:
        return []

    loc_country = {
        _norm(row.get("location_id")): _norm(row.get("event_country"))
        for _, row in location_df.iterrows()
        if _norm(row.get("location_id"))
    }

    counts: dict[tuple[str, str], int] = {}
    for _, row in results_df.iterrows():
        en = _norm(row.get("event_name"))
        lid = _norm(row.get("location_id"))
        if not en or not lid:
            continue
        hints = hint_countries_from_event_name(en)
        if not hints:
            continue
        country = loc_country.get(lid, "")
        if not country:
            continue
        if all(h != country for h in hints):
            key = (en, lid)
            counts[key] = counts.get(key, 0) + 1

    out: list[NameLocationConflict] = []
    for (en, lid), n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0][0])):
        out.append(
            NameLocationConflict(
                event_name=en,
                location_id=lid,
                location_country=loc_country.get(lid, ""),
                name_hints=tuple(hint_countries_from_event_name(en)),
                row_count=n,
            )
        )
    return out

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
    # Berlin events must not stay on Brno (shared location_id with Swing Fiction).
    (r"\bswinglab berlin\b|\bberlin swing revolution\b", "Germany"),
    # SaunaSwing is in Ikaalinen, Finland (not Wailea HI).
    (r"\bsaunaswing\b", "Finland"),
    # Sea Dance Fest is Moscow (not Düsseldorf).
    (r"\bsea dance fest\b", "Russia"),
    # Med in Swing is Côte d'Azur / France (not Phoenix AZ).
    (r"\bmed in swing\b", "France"),
    # Aloha Open is Hawaii / USA (not Jeju Korea).
    (r"\bthe aloha open\b|\baloha open\b", "United States"),
    # BTO / By-Town Open is Calgary / Canada (not Perth AU).
    (r"\bbto open\b|\bby-town open\b|\bcalgary town open\b", "Canada"),
    (r"\bbavarian open\b", "Germany"),
    (r"\bking swing\b|\bsanta swing\b", "Poland"),
    (r"\bwesty nantes\b", "France"),
    (r"\bparis westie fest\b", "France"),
    (r"\brolling swing\b", "France"),
    (r"\bdutch open\b", "Netherlands"),
    (r"\bwinter coast swing\b", "Finland"),
    # NZ Open must not stay on St. Petersburg (shared location_id 222).
    (r"\bnew zealand open\b|\bnew zealand west coast swing\b", "New Zealand"),
]


# Events whose scheduled location legitimately differs from historical results
# (series move / travelling event). Never auto-flag; needs year-aware handling.
KNOWN_SERIES_MOVES: frozenset[str] = frozenset(
    {
        "Westie's Angels",  # historical Washington DC results; 2026 schedule Lyon
        "Swingside Invitational",  # historical San Antonio; 2026 schedule Liège
    }
)

_COUNTRY_ALIASES = {
    "usa": "united states",
    "us": "united states",
    "uk": "united kingdom",
    "south korea": "republic of korea",
    "korea": "republic of korea",
    "nederland": "netherlands",
    "belgique": "belgium",
    "russian federation": "russia",
    # WSDC calendar typo (Finnfest: 'Helsinki, Uusimaa, Finalnd')
    "finalnd": "finland",
}


def normalize_country_label(value: object) -> str:
    """Lowercased country with common aliases collapsed ('GA United States' → 'united states')."""
    country = _norm(value).lower()
    if country in _COUNTRY_ALIASES:
        country = _COUNTRY_ALIASES[country]
    # 'GA United States', 'Hawaii/Maui, United States' tails etc.
    for canonical in ("united states", "united kingdom"):
        if country.endswith(canonical):
            return canonical
    return country


def country_from_location_text(text: object) -> str:
    """Last comma/slash-separated part of a location string, normalized."""
    parts = [p.strip() for p in re.split(r"[,/]", _norm(text)) if p.strip()]
    return normalize_country_label(parts[-1]) if parts else ""


@dataclass(frozen=True)
class NameLocationConflict:
    event_name: str
    location_id: str
    location_country: str
    name_hints: tuple[str, ...]
    row_count: int


@dataclass(frozen=True)
class ScheduledCountryConflict:
    event_name: str
    location_id: str
    results_country: str
    scheduled_country: str
    scheduled_location: str
    row_count: int


@dataclass(frozen=True)
class CatalogTypicalUpcomingConflict:
    canonical_name: str
    typical_location: str
    upcoming_location: str
    typical_country: str
    upcoming_country: str


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


def find_scheduled_country_conflicts(
    results_df: pd.DataFrame,
    location_df: pd.DataFrame,
    scheduled_df: pd.DataFrame,
    *,
    ignore_names: frozenset[str] = KNOWN_SERIES_MOVES,
) -> list[ScheduledCountryConflict]:
    """WSDC calendar country ≠ results mode-location country.

    Catches shared-wrong-location_id collisions with no name hints
    (Sea Dance Fest on Düsseldorf, Med in Swing on Phoenix, BTO on Perth).
    """
    if results_df is None or results_df.empty or scheduled_df is None or scheduled_df.empty:
        return []
    if location_df is None or location_df.empty:
        return []
    if "event_name" not in results_df.columns or "location_id" not in results_df.columns:
        return []

    loc_country = {
        _norm(row.get("location_id")): normalize_country_label(row.get("event_country"))
        for _, row in location_df.iterrows()
        if _norm(row.get("location_id"))
    }

    sched: dict[str, dict[str, str]] = {}
    for _, row in scheduled_df.iterrows():
        name = _norm(row.get("canonical_name")) or _norm(row.get("event_name"))
        if name:
            sched[name] = {
                "country": normalize_country_label(row.get("country")),
                "location_raw": _norm(row.get("location_raw")),
            }

    counts: dict[tuple[str, str], int] = {}
    for _, row in results_df.iterrows():
        en = _norm(row.get("event_name"))
        lid = _norm(row.get("location_id"))
        if en and lid:
            counts[(en, lid)] = counts.get((en, lid), 0) + 1

    mode_by_event: dict[str, tuple[str, int]] = {}
    for (en, lid), n in counts.items():
        if en not in mode_by_event or n > mode_by_event[en][1]:
            mode_by_event[en] = (lid, n)

    out: list[ScheduledCountryConflict] = []
    for en, (lid, n) in sorted(mode_by_event.items(), key=lambda kv: -kv[1][1]):
        if en in ignore_names:
            continue
        entry = sched.get(en)
        if not entry:
            continue
        expected = entry["country"]
        res_country = loc_country.get(lid, "")
        if not expected or not res_country or expected == res_country:
            continue
        if expected in res_country or res_country in expected:
            continue
        # US registry rows sometimes carry Canadian venues in location_raw.
        if expected == "united states" and res_country == "canada" and "canada" in entry["location_raw"].lower():
            continue
        out.append(
            ScheduledCountryConflict(
                event_name=en,
                location_id=lid,
                results_country=res_country,
                scheduled_country=expected,
                scheduled_location=entry["location_raw"],
                row_count=n,
            )
        )
    return out


def find_catalog_typical_upcoming_conflicts(
    catalog_df: pd.DataFrame,
    *,
    ignore_names: frozenset[str] = KNOWN_SERIES_MOVES,
) -> list[CatalogTypicalUpcomingConflict]:
    """Catalog typical_location country ≠ upcoming_location country.

    Freedom Swing pattern: typical stuck on a wrong shared location while the
    calendar (upcoming) is already correct. May also be a real series move —
    findings need research, not blind remap.
    """
    if catalog_df is None or catalog_df.empty:
        return []
    if "typical_location" not in catalog_df.columns or "upcoming_location" not in catalog_df.columns:
        return []

    out: list[CatalogTypicalUpcomingConflict] = []
    for _, row in catalog_df.iterrows():
        name = _norm(row.get("canonical_name"))
        if not name or name in ignore_names:
            continue
        typical = _norm(row.get("typical_location"))
        upcoming = _norm(row.get("upcoming_location"))
        if not typical or not upcoming:
            continue
        tc = country_from_location_text(typical) or normalize_country_label(row.get("typical_country"))
        uc = country_from_location_text(upcoming)
        if not tc or not uc or tc == uc:
            continue
        # skip US-state-abbrev artefacts ('az' vs 'united states')
        if len(tc) <= 3 or len(uc) <= 3:
            continue
        out.append(
            CatalogTypicalUpcomingConflict(
                canonical_name=name,
                typical_location=typical,
                upcoming_location=upcoming,
                typical_country=tc,
                upcoming_country=uc,
            )
        )
    return out

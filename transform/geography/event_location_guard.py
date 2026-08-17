"""Detect event-name vs location-country collisions (shared wrong location_id).

Classic failure: Westie Gala rows tagged with Wailea / Aloha Open (USA).
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
    # D-Town / WCS Festival at Boston Club venue → Germany (city fixed via merge/override).
    (r"\bd-town swing\b", "Germany"),
    (r"\bgerman open\b", "Germany"),
    (r"\bmilan modern swing\b", "Italy"),
    (r"\barousa westie fest\b", "Spain"),
    (r"\bvalentine swing\b|\bwestie gala\b|\bsweden westie gala\b|\buptown swing\b|\bswedish swing summer camp\b", "Sweden"),
]


# Events whose scheduled location legitimately differs from historical results
# (series move / travelling event). Never auto-flag; needs year-aware handling.
KNOWN_SERIES_MOVES: frozenset[str] = frozenset(
    {
        "Westie's Angels",  # historical Washington DC results; 2026 schedule Lyon
        "Swingside Invitational",  # historical San Antonio; 2026 schedule Liège
        # Toulouse 2023–2025; Paris CDG from 2026 (Soul Flow keeps Toulouse).
        "Global Grand Prix - West Coast Swing Reunion",
        "Global Grand Prix -- West Coast Swing Championships",
        "Global Grand Prix",
        # Pre-2025 Boston metro; 2025+ Mansfield venue.
        "Countdown Swing Boston",
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


@dataclass(frozen=True)
class EventIdCanonicalLocationMismatch:
    """Results/editions location disagrees with curated event_id canonical place."""

    event_id: str
    event_name: str
    canonical_source: str  # known | name_override | upcoming
    canonical_location: str
    canonical_country: str
    results_location_id: str
    results_country: str
    results_rows: int
    editions_location_id: str
    editions_country: str
    mismatch_side: str  # results | editions | both


def _countries_agree(a: str, b: str) -> bool:
    if not a or not b:
        return True
    if a == b:
        return True
    if a in b or b in a:
        return True
    return False


def build_event_id_canonical_locations(
    catalog_df: pd.DataFrame | None,
    *,
    known_metadata: dict[int, dict] | None = None,
    name_overrides: dict[str, str] | None = None,
) -> dict[str, tuple[str, str]]:
    """event_id → (canonical_location_text, source).

    Priority (curated first; never use results-derived typical alone):
    1. KNOWN_EVENT_METADATA[event_id].typical_location
    2. EVENT_NAME_LOCATION_OVERRIDES[canonical_name]
    3. event_catalog.upcoming_location (schedule-backed)
    """
    from transform.knowledge.events import (
        EVENT_NAME_LOCATION_OVERRIDES,
        KNOWN_EVENT_METADATA,
    )

    known = known_metadata if known_metadata is not None else KNOWN_EVENT_METADATA
    overrides = name_overrides if name_overrides is not None else EVENT_NAME_LOCATION_OVERRIDES

    out: dict[str, tuple[str, str]] = {}
    for eid, meta in known.items():
        loc = _norm((meta or {}).get("typical_location"))
        if loc:
            out[str(int(eid))] = (loc, "known")

    name_to_eid: dict[str, str] = {}
    upcoming_by_eid: dict[str, str] = {}
    if catalog_df is not None and not catalog_df.empty:
        for _, row in catalog_df.iterrows():
            eid = _norm(row.get("event_id"))
            name = _norm(row.get("canonical_name"))
            if eid and name:
                name_to_eid[name] = eid
            up = _norm(row.get("upcoming_location"))
            if eid and up:
                upcoming_by_eid[eid] = up

    for name, place in overrides.items():
        loc = _norm(place)
        eid = name_to_eid.get(_norm(name))
        if not eid or not loc or eid in out:
            continue
        out[eid] = (loc, "name_override")

    for eid, up in upcoming_by_eid.items():
        if eid not in out and up:
            out[eid] = (up, "upcoming")

    return out


def find_event_id_canonical_location_mismatches(
    results_df: pd.DataFrame,
    location_df: pd.DataFrame,
    catalog_df: pd.DataFrame | None,
    editions_df: pd.DataFrame | None = None,
    *,
    known_metadata: dict[int, dict] | None = None,
    name_overrides: dict[str, str] | None = None,
    ignore_names: frozenset[str] = KNOWN_SERIES_MOVES,
) -> list[EventIdCanonicalLocationMismatch]:
    """Flag when results/editions country ≠ curated event_id canonical country.

    Catches uniform shared-wrong location_id (all rows on one foreign id) that
    name-collision and name-hint audits miss. Requires a curated/upcoming canon;
    does not treat results-derived catalog.typical alone as truth.
    """
    if results_df is None or results_df.empty:
        return []
    if location_df is None or location_df.empty:
        return []
    if "event_name" not in results_df.columns or "location_id" not in results_df.columns:
        return []

    canonical = build_event_id_canonical_locations(
        catalog_df,
        known_metadata=known_metadata,
        name_overrides=name_overrides,
    )
    if not canonical:
        return []

    loc_country = {
        _norm(row.get("location_id")): normalize_country_label(row.get("event_country"))
        for _, row in location_df.iterrows()
        if _norm(row.get("location_id"))
    }

    eid_to_name: dict[str, str] = {}
    name_to_eid: dict[str, str] = {}
    if catalog_df is not None and not catalog_df.empty:
        for _, row in catalog_df.iterrows():
            eid = _norm(row.get("event_id"))
            name = _norm(row.get("canonical_name"))
            if eid and name:
                eid_to_name[eid] = name
                name_to_eid[name] = eid

    # results mode lid by event_id (prefer event_name_id, else name→catalog)
    id_col = "event_name_id" if "event_name_id" in results_df.columns else None
    counts: dict[str, dict[str, int]] = {}
    for _, row in results_df.iterrows():
        en = _norm(row.get("event_name"))
        lid = _norm(row.get("location_id"))
        if not en or not lid:
            continue
        if en in ignore_names:
            continue
        eid = ""
        if id_col:
            raw_eid = _norm(row.get(id_col))
            if raw_eid.isdigit():
                eid = str(int(raw_eid))
        if not eid:
            eid = name_to_eid.get(en, "")
        if not eid or eid not in canonical:
            continue
        bucket = counts.setdefault(eid, {})
        bucket[lid] = bucket.get(lid, 0) + 1

    results_mode: dict[str, tuple[str, int]] = {}
    for eid, lids in counts.items():
        lid, n = max(lids.items(), key=lambda kv: kv[1])
        results_mode[eid] = (lid, n)

    editions_mode: dict[str, tuple[str, int]] = {}
    if editions_df is not None and not editions_df.empty and "event_id" in editions_df.columns:
        ed_counts: dict[str, dict[str, int]] = {}
        for _, row in editions_df.iterrows():
            eid = _norm(row.get("event_id"))
            lid = _norm(row.get("location_id"))
            if not eid or not lid or eid not in canonical:
                continue
            name = eid_to_name.get(eid, _norm(row.get("event_name")))
            if name in ignore_names:
                continue
            bucket = ed_counts.setdefault(eid, {})
            bucket[lid] = bucket.get(lid, 0) + 1
        for eid, lids in ed_counts.items():
            lid, n = max(lids.items(), key=lambda kv: kv[1])
            editions_mode[eid] = (lid, n)

    out: list[EventIdCanonicalLocationMismatch] = []
    for eid, (canon_loc, source) in sorted(canonical.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0):
        name = eid_to_name.get(eid, "")
        if name in ignore_names:
            continue
        expected_country = country_from_location_text(canon_loc)
        if not expected_country:
            continue

        res_lid, res_n = results_mode.get(eid, ("", 0))
        res_country = loc_country.get(res_lid, "") if res_lid else ""
        ed_lid, _ed_n = editions_mode.get(eid, ("", 0))
        ed_country = loc_country.get(ed_lid, "") if ed_lid else ""

        res_bad = bool(res_lid and res_country and not _countries_agree(expected_country, res_country))
        ed_bad = bool(ed_lid and ed_country and not _countries_agree(expected_country, ed_country))
        if not res_bad and not ed_bad:
            continue
        side = "both" if res_bad and ed_bad else ("results" if res_bad else "editions")
        out.append(
            EventIdCanonicalLocationMismatch(
                event_id=eid,
                event_name=name or f"event_id:{eid}",
                canonical_source=source,
                canonical_location=canon_loc,
                canonical_country=expected_country,
                results_location_id=res_lid,
                results_country=res_country,
                results_rows=res_n,
                editions_location_id=ed_lid,
                editions_country=ed_country,
                mismatch_side=side,
            )
        )

    out.sort(key=lambda c: (-c.results_rows, c.event_id))
    return out

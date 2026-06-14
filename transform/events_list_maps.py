"""Cosmetic cleanup for location strings scraped from worldsdc.com/events/."""

from __future__ import annotations

import re

# Exact scrape typos / formatting fixes (not venue overrides)
EVENTS_LIST_LOCATION_EXACT: dict[str, str] = {
    "Zurich,  Swintzerland": "Zürich, Switzerland",
    "Kraków, malopolska, Polska": "Kraków, Poland",
    "LYON France, Rhones, France": "Lyon, Rhone, France",
    "LYON, Rhones, France": "Lyon, Rhone, France",
    "Bonn, Nordrhein-Westphalen, Germany": "Bonn, Germany",
    "Milan,, Italy": "Milan, Italy",
    "Berlin,  Germany": "Berlin, Germany",
    "Hamburg,  Germany": "Hamburg, Germany",
    "London,  UK": "London, UK",
    "Ft. Lauderdale, FL, United States": "Fort Lauderdale, FL, United States",
    "Deutschland , Germany": "Germany",
    "Albany, NY, Albany": "Albany, NY, United States",
    "San antonio, Texas, United states": "San Antonio, TX, United States",
}

# Substring replacements (order matters)
EVENTS_LIST_LOCATION_SUBSTRINGS: list[tuple[str, str]] = [
    ("Czechia", "Czech Republic"),
    ("Sverige", "Sweden"),
    ("The Netherland", "The Netherlands"),
    ("Russian Federation", "Russia"),
    ("United States of America", "United States"),
    ("USA", "United States"),
    (", n/a,", ", "),
    (",  ", ", "),
]

_COUNTRY_ALIASES: dict[str, str] = {
    "russian federation": "Russia",
    "korea, republic of": "Republic of Korea",
    "united states of america": "United States",
    "uk": "United Kingdom",
    "u.s.a.": "United States",
    "us": "United States",
    "usa": "United States",
    "deutschland": "Germany",
    "polska": "Poland",
    "bulgaria": "Bulgaria",
    "romania": "Romania",
    "latvia": "Latvia",
    "malaysia": "Malaysia",
    "russia": "Russia",
    "england": "United Kingdom",
    "scotland": "United Kingdom",
    "wales": "United Kingdom",
}

# US/CA/AU state & province codes — when last segment is a code, infer country from context.
_SUBNATIONAL_CODES: dict[str, str] = {
    **{code: "United States" for code in (
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
        "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT",
        "VA", "WA", "WV", "WI", "WY", "DC",
    )},
    **{code: "Canada" for code in ("AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT")},
}


def _normalize_country_token(token: str) -> str:
    key = token.strip().lower()
    if not key:
        return ""
    if key in _COUNTRY_ALIASES:
        return _COUNTRY_ALIASES[key]
    return token.strip()


def country_from_location(location_raw: str) -> str:
    """Infer country from location text when worldsdc.com omits the flag icon."""
    loc = clean_list_location(location_raw)
    if not loc:
        return ""

    parts = [p.strip() for p in loc.split(",") if p.strip()]
    if not parts:
        return ""

    if len(parts) == 1:
        return _normalize_country_token(parts[0])

    if any(p.strip().lower() in ("united states", "united states of america") for p in parts):
        return "United States"
    if any(p.strip().lower() in ("united kingdom", "great britain") for p in parts):
        return "United Kingdom"

    last = parts[-1]
    last_up = last.upper()
    if last_up in _SUBNATIONAL_CODES:
        return _SUBNATIONAL_CODES[last_up]

    return _normalize_country_token(last)


def _collapse_commas(loc: str) -> str:
    loc = re.sub(r",\s*,+", ",", loc)
    loc = re.sub(r"\s+", " ", loc)
    return loc.strip(" ,")


def _normalize_us_location_parts(parts: list[str]) -> list[str]:
    """Ensure US rows use City, ST, United States when a state code is present."""
    if len(parts) < 2:
        return parts

    city = parts[0].strip()
    state_token = parts[1].strip()
    state_up = state_token.upper()

    if state_up not in _SUBNATIONAL_CODES or _SUBNATIONAL_CODES[state_up] != "United States":
        return parts

    us_country = {"united states", "usa", "us", "united states of america"}
    if len(parts) == 2:
        return [city, state_up, "United States"]

    last = parts[-1].strip().lower()
    if last in us_country:
        normalized = [city, state_up, "United States"]
        return normalized

    # WSDC typo: "Albany, NY, Albany" — city repeated instead of country
    if parts[-1].strip().lower() == city.lower():
        return [city, state_up, "United States"]

    return [city, state_up, "United States"]


def clean_list_location(location_raw: str) -> str:
    """Clean scrape text only — no per-event venue overrides."""
    loc = (location_raw or "").strip()
    if not loc:
        return loc

    if loc in EVENTS_LIST_LOCATION_EXACT:
        loc = EVENTS_LIST_LOCATION_EXACT[loc]

    for old, new in EVENTS_LIST_LOCATION_SUBSTRINGS:
        if old in loc:
            loc = loc.replace(old, new)

    loc = _collapse_commas(loc)

    # Normalize trailing country duplicates e.g. "Bucharest, Romania, Bucharest, Romania"
    parts = [p.strip() for p in loc.split(",") if p.strip()]
    if len(parts) >= 4 and parts[0] == parts[2] and parts[1] == parts[3]:
        loc = ", ".join(parts[:2])

    parts = [p.strip() for p in loc.split(",") if p.strip()]
    if parts:
        parts = _normalize_us_location_parts(parts)
        loc = ", ".join(parts)

    lower = loc.lower()
    for alias, canonical in _COUNTRY_ALIASES.items():
        if lower.endswith(alias):
            loc = loc[: -len(alias)] + canonical
            break

    return _collapse_commas(loc)


def normalize_list_location(_event_name: str, location_raw: str) -> str:
    """Backward-compatible wrapper; event_name is ignored (site text wins)."""
    return clean_list_location(location_raw)

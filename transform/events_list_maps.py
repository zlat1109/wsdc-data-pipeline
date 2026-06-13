"""Location and name maps for WSDC Events List (from legacy dashboard parser)."""

from __future__ import annotations

import re

# By canonical event name (after name cleaning)
EVENTS_LIST_LOCATION_BY_EVENT: dict[str, str] = {
    "Avignon City Swing": "Gard, France",
    "Asia West Coast Swing Open": "Singapore",
    "Sea Dance Fest": "Anapa, Russia",
    "Swing Fling": "Herndon, VA",
    "Swingtzerland": "Zürich, Switzerland",
    "Easter Swing": "Seattle, WA",
}

# Exact location string fixes
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
}


def _collapse_commas(loc: str) -> str:
    loc = re.sub(r",\s*,+", ",", loc)
    loc = re.sub(r"\s+", " ", loc)
    return loc.strip(" ,")


def normalize_list_location(event_name: str, location_raw: str) -> str:
    """Apply known location fixes for events list strings."""
    loc = (location_raw or "").strip()
    if not loc:
        return loc

    if event_name in EVENTS_LIST_LOCATION_BY_EVENT:
        loc = EVENTS_LIST_LOCATION_BY_EVENT[event_name]

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

    lower = loc.lower()
    for alias, canonical in _COUNTRY_ALIASES.items():
        if lower.endswith(alias):
            loc = loc[: -len(alias)] + canonical
            break

    return _collapse_commas(loc)

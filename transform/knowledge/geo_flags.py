"""Country → continent / flag maps for Point Summary entities.

Prefer the normalized `place_country` from `event_editions` / `location_info`.
Free-text location parsing is only a fallback for incomplete rows.
"""

from __future__ import annotations

import re

# Two-letter US state codes must never match as substrings of country names.
_US_STATE_ABBREVS = (
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
)
US_STATE_CODES = frozenset(_US_STATE_ABBREVS)
COMMA_FIELD_LOCALE_CODES = US_STATE_CODES | {"US", "UK"}

COUNTRY_TO_CONTINENT: dict[str, str] = {
    "Austria": "Europe",
    "Belgium": "Europe",
    "Bulgaria": "Europe",
    "Czech Republic": "Europe",
    "Czechia": "Europe",
    "Estonia": "Europe",
    "Finland": "Europe",
    "France": "Europe",
    "Germany": "Europe",
    "Deutschland": "Europe",
    "Hungary": "Europe",
    "Ireland": "Europe",
    "Italy": "Europe",
    "Latvia": "Europe",
    "Netherlands": "Europe",
    "The Netherlands": "Europe",
    "Nederland": "Europe",
    "Norway": "Europe",
    "Poland": "Europe",
    "Polska": "Europe",
    "Portugal": "Europe",
    "Romania": "Europe",
    "Russia": "Europe",
    "Slovenia": "Europe",
    "Spain": "Europe",
    "Sweden": "Europe",
    "Switzerland": "Europe",
    "Ukraine": "Europe",
    "United Kingdom": "Europe",
    "UK": "Europe",
    "England": "Europe",
    "Scotland": "Europe",
    "Wales": "Europe",
    "Russian Federation": "Europe",
    "United States": "America",
    "Canada": "America",
    "New York": "America",
    "Australia": "Australia",
    "New Zealand": "Australia",
    "Malaysia": "Asia",
    "Singapore": "Asia",
    "Republic of Korea": "Asia",
    "South Korea": "Asia",
    "North Korea": "Asia",
    "Israel": "Asia",
    "Japan": "Asia",
    "China": "Asia",
    "Thailand": "Asia",
    "Brazil": "South America",
    "Denmark": "Europe",
    "Croatia": "Europe",
    "Greece": "Europe",
    "Lithuania": "Europe",
    "Slovakia": "Europe",
}

COUNTRY_TO_FLAG: dict[str, str] = {
    "United States": "🇺🇸",
    "USA": "🇺🇸",
    "U.S.A.": "🇺🇸",
    "US": "🇺🇸",
    "Canada": "🇨🇦",
    "Poland": "🇵🇱",
    "Polska": "🇵🇱",
    "Sweden": "🇸🇪",
    "Norway": "🇳🇴",
    "Germany": "🇩🇪",
    "Deutschland": "🇩🇪",
    "France": "🇫🇷",
    "United Kingdom": "🇬🇧",
    "UK": "🇬🇧",
    "England": "🇬🇧",
    "Scotland": "🇬🇧",
    "Wales": "🇬🇧",
    "Australia": "🇦🇺",
    "South Australia": "🇦🇺",
    "Singapore": "🇸🇬",
    "Hungary": "🇭🇺",
    "Russia": "🇷🇺",
    "Russian Federation": "🇷🇺",
    "Austria": "🇦🇹",
    "Spain": "🇪🇸",
    "Italy": "🇮🇹",
    "Netherlands": "🇳🇱",
    "The Netherlands": "🇳🇱",
    "Nederland": "🇳🇱",
    "Belgium": "🇧🇪",
    "Czech Republic": "🇨🇿",
    "Czechia": "🇨🇿",
    "Switzerland": "🇨🇭",
    "Portugal": "🇵🇹",
    "Finland": "🇫🇮",
    "Denmark": "🇩🇰",
    "Ireland": "🇮🇪",
    "Slovenia": "🇸🇮",
    "Croatia": "🇭🇷",
    "Bulgaria": "🇧🇬",
    "Romania": "🇷🇴",
    "Greece": "🇬🇷",
    "Latvia": "🇱🇻",
    "Estonia": "🇪🇪",
    "Lithuania": "🇱🇹",
    "Slovakia": "🇸🇰",
    "New Zealand": "🇳🇿",
    "Malaysia": "🇲🇾",
    "Japan": "🇯🇵",
    "Republic of Korea": "🇰🇷",
    "South Korea": "🇰🇷",
    "North Korea": "🇰🇵",
    "China": "🇨🇳",
    "Thailand": "🇹🇭",
    "Brazil": "🇧🇷",
    "Israel": "🇮🇱",
    "Ukraine": "🇺🇦",
    "New York": "🇺🇸",
}

for _state in US_STATE_CODES:
    COUNTRY_TO_CONTINENT.setdefault(_state, "America")
    COUNTRY_TO_FLAG.setdefault(_state, "🇺🇸")


def _us_state_after_comma(location_lower: str, code: str) -> bool:
    c = code.lower()
    return bool(re.search(r",\s*" + re.escape(c) + r"(?:\s*,|\s*$)", location_lower))


def continent_for_country(country: str | None) -> str:
    """Map a normalized country name to a Point Summary continent label."""
    if not country:
        return "America"
    key = str(country).strip()
    if key in COUNTRY_TO_CONTINENT:
        return COUNTRY_TO_CONTINENT[key]
    for name, continent in COUNTRY_TO_CONTINENT.items():
        if name.lower() == key.lower():
            return continent
    return "America"


def flag_for_country(country: str | None) -> str:
    """Map a normalized country name to a flag emoji."""
    if not country:
        return "🌍"
    key = str(country).strip()
    if key in COUNTRY_TO_FLAG:
        return COUNTRY_TO_FLAG[key]
    for name, flag in COUNTRY_TO_FLAG.items():
        if name.lower() == key.lower():
            return flag
    return "🌍"


def continent_from_location_text(location: str | None) -> str:
    """Fallback when place_country is missing: scan free-text location."""
    if not location:
        return "America"
    location_lower = location.lower()
    if "zurich" in location_lower or "zürich" in location_lower:
        return "Europe"
    for country, continent in sorted(
        COUNTRY_TO_CONTINENT.items(), key=lambda x: len(x[0]), reverse=True
    ):
        if country in COMMA_FIELD_LOCALE_CODES:
            if _us_state_after_comma(location_lower, country):
                return continent
            continue
        if country.lower() in location_lower:
            return continent
    return "America"


def flag_from_location_text(location: str | None) -> str:
    """Fallback flag from free-text location."""
    if not location:
        return "🌍"
    location_lower = location.lower()
    if "zurich" in location_lower or "zürich" in location_lower:
        return "🇨🇭"
    for country, flag in sorted(
        COUNTRY_TO_FLAG.items(), key=lambda x: len(x[0]), reverse=True
    ):
        if country in COMMA_FIELD_LOCALE_CODES:
            if _us_state_after_comma(location_lower, country):
                return flag
            continue
        if country.lower() in location_lower:
            return flag
    return "🌍"


def resolve_flag_and_continent(
    *,
    country: str | None = None,
    location: str | None = None,
) -> tuple[str, str]:
    """Prefer normalized country; fall back to location text."""
    if country and str(country).strip():
        return flag_for_country(country), continent_for_country(country)
    return flag_from_location_text(location), continent_from_location_text(location)

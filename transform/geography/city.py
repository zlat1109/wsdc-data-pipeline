"""City display normalization for location_info and derived exports."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional

import pandas as pd

from transform.geography.constants import STATE_CODE_TO_NAME, STATE_NAME_TO_CODE

if TYPE_CHECKING:
    from transform.preprocess_tracker import PreprocessTracker

_LOWercase_PARTICLES = frozenset({"de", "la", "le", "van", "von", "den", "am", "sur", "saint"})


def _strip_city_punctuation(city: str) -> str:
    return str(city).strip().strip(",").strip()


EMBEDDED_STATE_TOKENS: dict[str, str] = {
    **STATE_CODE_TO_NAME,
    "DEL": "Delaware",
}


def split_embedded_us_state_from_city(city: str) -> tuple[str, Optional[str]]:
    """Split trailing US state code from city (e.g. WILMINGTON DEL -> Wilmington)."""
    city = _strip_city_punctuation(city)
    if not city:
        return "", None

    parts = city.split()
    if len(parts) >= 2:
        last = parts[-1].upper()
        if last in EMBEDDED_STATE_TOKENS:
            name = " ".join(parts[:-1]).strip()
            if name:
                return name, EMBEDDED_STATE_TOKENS[last]
    return city, None


def _title_token(token: str) -> str:
    if not token:
        return token
    if token.isupper() and len(token) <= 3 and token.isalpha():
        return token

    lower = token.lower()
    if lower.startswith("st.") and len(token) > 3:
        return "St." + token[3:].title()
    if lower == "st":
        return "St."
    if lower.startswith("st-"):
        return "St-" + token[3:].title()
    if lower.startswith("mc") and len(token) > 2:
        return "Mc" + token[2:].title()
    if lower.startswith("mac") and len(token) > 3:
        return "Mac" + token[3:].title()
    if lower.startswith("o'") and len(token) > 2:
        return "O'" + token[2:].title()
    return token.title()


def normalize_city_display(city: str, *, index: int = 0) -> str:
    """Title-case city names; preserve intentional mixed case."""
    city = _strip_city_punctuation(city)
    if not city:
        return ""

    if city != city.upper() and city != city.lower():
        return city

    parts = re.split(r"(\s+|-)", city)
    out: list[str] = []
    word_index = 0
    for part in parts:
        if not part or part.isspace() or part == "-":
            out.append(part)
            continue
        if part.lower() in _LOWercase_PARTICLES and word_index > 0:
            out.append(part.lower())
        else:
            out.append(_title_token(part))
        word_index += 1
    return "".join(out)


def normalize_city_field(city: str) -> tuple[str, Optional[str]]:
    """Normalize city and optionally extract embedded US state."""
    city = _strip_city_punctuation(city)
    if not city:
        return "", None

    name, extracted_state = split_embedded_us_state_from_city(city)
    return normalize_city_display(name), extracted_state


def normalize_location_whitespace(text: str) -> str:
    """Collapse duplicate spaces in display location strings."""
    if not text:
        return ""
    return re.sub(r"\s{2,}", " ", str(text).strip())


def format_event_location(row: pd.Series) -> str:
    city = _strip_city_punctuation(str(row.get("event_city", "")).strip())
    state = str(row.get("event_state", "")).strip() if pd.notna(row.get("event_state")) else ""
    country = str(row.get("event_country", "")).strip() if pd.notna(row.get("event_country")) else ""

    if not city:
        return normalize_location_whitespace(str(row.get("event_location", "")).strip())

    if country in {"United States", "USA", "US"}:
        if state:
            code = STATE_NAME_TO_CODE.get(state, state)
            if len(code) == 2:
                return normalize_location_whitespace(f"{city}, {code}, United States")
            return normalize_location_whitespace(f"{city}, {state}, United States")
        return normalize_location_whitespace(f"{city}, United States")

    if country:
        if state:
            return normalize_location_whitespace(f"{city}, {state}, {country}")
        return normalize_location_whitespace(f"{city}, {country}")
    return normalize_location_whitespace(city)


def replace_city_in_location_string(location: str, old_city: str, new_city: str) -> str:
    if not location or not old_city or old_city == new_city:
        return location
    pattern = re.compile(re.escape(old_city.strip()), re.IGNORECASE)
    return pattern.sub(new_city, location, count=1)


def apply_city_normalization_to_frame(
    df: pd.DataFrame,
    tracker: PreprocessTracker | None = None,
) -> pd.DataFrame:
    out, _ = apply_city_normalization_with_replacements(df, tracker)
    return out


def apply_city_normalization_with_replacements(
    df: pd.DataFrame,
    tracker: PreprocessTracker | None = None,
) -> tuple[pd.DataFrame, dict[str, str]]:
    if "event_city" not in df.columns:
        return df, {}

    out = df.copy()
    changed = 0
    replacements: dict[str, str] = {}

    for idx, row in out.iterrows():
        raw_city = row.get("event_city")
        if pd.isna(raw_city) or not str(raw_city).strip():
            continue

        old_city = str(raw_city).strip()
        clean_old = _strip_city_punctuation(old_city)
        new_city, extracted_state = normalize_city_field(old_city)
        if not new_city:
            continue

        row_changed = clean_old != old_city or new_city != clean_old
        if extracted_state:
            current_state = str(row.get("event_state", "")).strip() if pd.notna(row.get("event_state")) else ""
            if not current_state:
                out.at[idx, "event_state"] = extracted_state
                row_changed = True

        if row_changed:
            out.at[idx, "event_city"] = new_city
            if "event_location" in out.columns:
                old_location = str(row.get("event_location", "")).strip()
                new_location = format_event_location(out.loc[idx])
                out.at[idx, "event_location"] = new_location
                if old_location and old_location != new_location:
                    replacements[old_location.upper()] = new_location
            if "event_location_standardized" in out.columns:
                old_std = str(row.get("event_location_standardized", "")).strip()
                new_std = format_event_location(out.loc[idx])
                if "event_state" in out.columns and out.at[idx, "event_state"]:
                    code = STATE_NAME_TO_CODE.get(str(out.at[idx, "event_state"]).strip())
                    if code and len(code) == 2:
                        new_std = f"{new_city}, {code}"
                out.at[idx, "event_location_standardized"] = new_std
                if old_std and old_std != new_std:
                    replacements[old_std.upper()] = new_std
            changed += 1

    if tracker is not None and changed:
        tracker.record(
            "CITY_DISPLAY_NORMALIZATION",
            "location_info",
            "event_city",
            "ALL CAPS / embedded state / trailing punctuation",
            "Title Case city",
            changed,
            "city_normalize",
        )

    return out, replacements


def location_lookup(location_df: pd.DataFrame) -> dict[int, dict[str, str]]:
    lookup: dict[int, dict[str, str]] = {}
    for _, row in location_df.iterrows():
        location_id = row.get("location_id")
        if pd.isna(location_id):
            continue
        lookup[int(location_id)] = {
            "event_city": _strip_city_punctuation(str(row.get("event_city", "")).strip()),
            "event_state": str(row.get("event_state", "")).strip() if pd.notna(row.get("event_state")) else "",
            "event_country": str(row.get("event_country", "")).strip() if pd.notna(row.get("event_country")) else "",
            "event_location": str(row.get("event_location", "")).strip() if pd.notna(row.get("event_location")) else "",
            "event_location_standardized": str(row.get("event_location_standardized", "")).strip()
            if pd.notna(row.get("event_location_standardized"))
            else "",
        }
    return lookup


def apply_string_replacement(text: str, string_replacements: dict[str, str]) -> str:
    """Apply known location string fixes (city normalization); never invent a new venue."""
    stripped = _strip_city_punctuation(str(text).strip())
    if not stripped:
        return stripped
    return string_replacements.get(stripped.upper(), stripped)


def sync_upcoming_location_string(
    upcoming: str,
    typical: str,
    *,
    string_replacements: dict[str, str],
) -> str:
    """Normalize upcoming location without overwriting a genuinely different venue."""
    upcoming = normalize_location_whitespace(str(upcoming or "").strip())
    typical = normalize_location_whitespace(str(typical or "").strip())
    if not upcoming:
        return upcoming

    replaced = apply_string_replacement(upcoming, string_replacements)
    if replaced != upcoming:
        return normalize_location_whitespace(replaced)

    if typical and upcoming != typical and upcoming.upper() == typical.upper():
        return typical

    return upcoming


def sync_typical_location_from_edition(
    current_typical: str,
    edition_location_raw: str,
    *,
    string_replacements: dict[str, str],
) -> str:
    """Update catalog typical from edition mode location without clobbering venue metadata."""
    edition_raw = normalize_location_whitespace(str(edition_location_raw or "").strip())
    current = normalize_location_whitespace(str(current_typical or "").strip())
    if not edition_raw:
        return current
    if not current:
        return edition_raw

    replaced = apply_string_replacement(edition_raw, string_replacements)
    if replaced != edition_raw:
        edition_raw = normalize_location_whitespace(replaced)

    if current.upper() == edition_raw.upper():
        return current

    if current != edition_raw:
        return current

    return edition_raw

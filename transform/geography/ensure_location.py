"""Ensure a location_info row (+ coords) from free-text city/country.

Used for trial / list events that lack results-backed geo. Never overwrites
existing location_id or non-empty coordinates on a matched row.

Source vocabulary (priority for future website scrape):
  event_website > events_list resolve path below > points
MVP sources: location_info | city_canonical | google_maps | unresolved
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Callable

import pandas as pd

from transform.geography.canonical import CITY_CANONICAL_COORDINATES
from transform.geography.resolve import (
    LOCATION_COLUMNS,
    _canonical_location_raw,
    _parse_location_parts,
    build_location_lookup,
    location_lookup_key_from_text,
)
from transform.geography.utils import norm_value

logger = logging.getLogger(__name__)

SOURCE_LOCATION_INFO = "location_info"
SOURCE_CITY_CANONICAL = "city_canonical"
SOURCE_GOOGLE_MAPS = "google_maps"
SOURCE_UNRESOLVED = "unresolved"

GeocodeFn = Callable[[str], tuple[float, float] | None]


@dataclass(frozen=True)
class EnsureLocationResult:
    location_id: str | None
    source: str
    created: bool = False
    coords_filled: bool = False
    review_reason: str | None = None


def google_geocode(query: str) -> tuple[float, float] | None:
    """Geocode via Google Maps when GOOGLE_MAPS_API_KEY is set."""
    key = (os.getenv("GOOGLE_MAPS_API_KEY") or "").strip()
    if not key or not query.strip():
        return None
    try:
        import googlemaps
    except ImportError:
        logger.warning("googlemaps package not installed; skipping Google geocode")
        return None
    try:
        client = googlemaps.Client(key=key)
        results = client.geocode(query)
        if not results:
            return None
        loc = results[0]["geometry"]["location"]
        return float(loc["lat"]), float(loc["lng"])
    except Exception as exc:  # noqa: BLE001 — network/API failures stay soft
        logger.debug("Google geocode failed for %r: %s", query, exc)
        return None


def _coords_valid(lat: object, lon: object) -> bool:
    try:
        if lat is None or lon is None:
            return False
        lat_s, lon_s = str(lat).strip(), str(lon).strip()
        if not lat_s or not lon_s or lat_s.lower() == "nan" or lon_s.lower() == "nan":
            return False
        float(lat_s)
        float(lon_s)
        return True
    except (TypeError, ValueError):
        return False


def _canonical_coords(city: str, state: str, country: str) -> tuple[float, float] | None:
    city, state, country = city.strip(), state.strip(), country.strip()
    if not city or not country:
        return None
    if country == "United States" and state:
        key = (city, country, state)
    else:
        key = (city, country, "")
    return CITY_CANONICAL_COORDINATES.get(key)


def _coords_from_city_country(
    location_df: pd.DataFrame, city: str, country: str
) -> tuple[float, float] | None:
    """Reuse lat/lon from any location_info row with same city+country."""
    if location_df is None or location_df.empty or not city or not country:
        return None
    city_l = city.strip().lower()
    country_l = country.strip().lower()
    for _, row in location_df.iterrows():
        if str(row.get("event_city") or "").strip().lower() != city_l:
            continue
        if str(row.get("event_country") or "").strip().lower() != country_l:
            continue
        if _coords_valid(row.get("latitude"), row.get("longitude")):
            return float(row["latitude"]), float(row["longitude"])
    return None


def _find_id_by_city_country(
    location_df: pd.DataFrame, city: str, country: str
) -> str | None:
    if location_df is None or location_df.empty or not city or not country:
        return None
    city_l = city.strip().lower()
    country_l = country.strip().lower()
    best: str | None = None
    best_num = 10**18
    for _, row in location_df.iterrows():
        if str(row.get("event_city") or "").strip().lower() != city_l:
            continue
        if str(row.get("event_country") or "").strip().lower() != country_l:
            continue
        lid = str(row.get("location_id") or "").strip()
        if not lid:
            continue
        try:
            n = int(lid)
        except ValueError:
            n = best_num
        if best is None or n < best_num:
            best, best_num = lid, n
    return best


def _next_location_id(location_df: pd.DataFrame) -> str:
    ids = pd.to_numeric(
        location_df.get("location_id", pd.Series(dtype=str)), errors="coerce"
    )
    max_id = int(ids.max()) if ids.notna().any() else 0
    return str(max_id + 1)


def _row_by_id(location_df: pd.DataFrame, loc_id: str) -> pd.Series | None:
    mask = location_df["location_id"].astype(str).str.strip() == str(loc_id)
    if not mask.any():
        return None
    return location_df.loc[mask].iloc[0]


def ensure_location(
    location_raw: str,
    *,
    country: str = "",
    location_df: pd.DataFrame,
    geocode_fn: GeocodeFn | None = None,
    allow_create: bool = True,
    allow_geocode: bool = True,
) -> tuple[EnsureLocationResult, pd.DataFrame]:
    """Match or create a location row; fill blank coords without overwriting.

    Returns (result, possibly-updated location_df).
    """
    raw = _canonical_location_raw(norm_value(location_raw))
    if not raw:
        return (
            EnsureLocationResult(
                None, SOURCE_UNRESOLVED, review_reason="empty_location_raw"
            ),
            location_df,
        )

    if location_df is None:
        location_df = pd.DataFrame(columns=LOCATION_COLUMNS)
    else:
        location_df = location_df.copy()

    lookup = build_location_lookup(location_df)
    key = location_lookup_key_from_text(raw)
    loc_id = lookup.get(key) or lookup.get(raw.lower())

    city, state, parsed_country = _parse_location_parts(raw)
    country_use = (standardize_or_keep(country) or parsed_country or "").strip()
    if not city and country_use:
        city = ""

    if not loc_id and city and (country_use or parsed_country):
        loc_id = _find_id_by_city_country(
            location_df, city, country_use or parsed_country
        )

    geocode = geocode_fn if geocode_fn is not None else google_geocode
    query = raw if not country_use or country_use.lower() in raw.lower() else f"{raw}, {country_use}"

    if loc_id:
        row = _row_by_id(location_df, loc_id)
        if row is not None and _coords_valid(row.get("latitude"), row.get("longitude")):
            return (
                EnsureLocationResult(str(loc_id), SOURCE_LOCATION_INFO),
                location_df,
            )
        # Matched place but missing coords — fill only blanks
        coords, src = _resolve_coords(
            city,
            state,
            country_use or parsed_country,
            query,
            location_df,
            geocode,
            allow_geocode,
        )
        if coords and row is not None:
            mask = location_df["location_id"].astype(str).str.strip() == str(loc_id)
            location_df.loc[mask, "latitude"] = coords[0]
            location_df.loc[mask, "longitude"] = coords[1]
            location_df.loc[mask, "coordinates_valid"] = "t"
            return (
                EnsureLocationResult(str(loc_id), src, coords_filled=True),
                location_df,
            )
        return (
            EnsureLocationResult(
                str(loc_id),
                SOURCE_LOCATION_INFO,
                review_reason="matched_without_coords",
            ),
            location_df,
        )

    if not allow_create:
        return (
            EnsureLocationResult(
                None, SOURCE_UNRESOLVED, review_reason="no_match_create_disabled"
            ),
            location_df,
        )

    coords, src = _resolve_coords(
        city,
        state,
        country_use or parsed_country,
        query,
        location_df,
        geocode,
        allow_geocode,
    )
    new_id = _next_location_id(location_df)
    event_location = raw
    new_row = {
        "location_id": new_id,
        "event_city": city,
        "event_state": state,
        "event_country": country_use or parsed_country,
        "latitude": coords[0] if coords else "",
        "longitude": coords[1] if coords else "",
        "event_location": event_location,
        "event_location_standardized": event_location,
        "coordinates_valid": "t" if coords else "",
    }
    cols = list(location_df.columns) if len(location_df.columns) else LOCATION_COLUMNS
    appended = pd.DataFrame([new_row]).reindex(columns=cols, fill_value="")
    location_df = pd.concat([location_df, appended], ignore_index=True)
    review = None if coords else "created_without_coords"
    return (
        EnsureLocationResult(
            new_id,
            src if coords else SOURCE_UNRESOLVED,
            created=True,
            coords_filled=bool(coords),
            review_reason=review,
        ),
        location_df,
    )


def standardize_or_keep(country: str) -> str:
    from transform.geography.normalize import standardize_country

    text = norm_value(country)
    if not text:
        return ""
    return standardize_country(text) or text


def _resolve_coords(
    city: str,
    state: str,
    country: str,
    query: str,
    location_df: pd.DataFrame,
    geocode: GeocodeFn,
    allow_geocode: bool,
) -> tuple[tuple[float, float] | None, str]:
    canon = _canonical_coords(city, state, country)
    if canon:
        return canon, SOURCE_CITY_CANONICAL
    reused = _coords_from_city_country(location_df, city, country)
    if reused:
        return reused, SOURCE_LOCATION_INFO
    if allow_geocode:
        got = geocode(query)
        if got:
            return got, SOURCE_GOOGLE_MAPS
    return None, SOURCE_UNRESOLVED

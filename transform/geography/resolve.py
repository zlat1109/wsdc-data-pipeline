"""Resolve numeric location_id for result rows from the location_info table.

The WSDC lookup API returns each event's place as a raw string (event.location,
e.g. "Boston, MA, United States") but no numeric location_id. The legacy notebook
workflow joined results.event_location -> location_info to recover location_id and
appended new locations with sequential ids. This module reproduces that join so
core.results.location_id is populated again (it was NULL after the HTTP cloud
parser dropped the field).
"""

from __future__ import annotations

import pandas as pd

from transform.geography.normalize import (
    parse_us_state_from_location_text,
    standardize_country,
)

LOCATION_COLUMNS = [
    "location_id",
    "event_city",
    "event_state",
    "event_country",
    "latitude",
    "longitude",
    "event_location",
    "event_location_standardized",
    "coordinates_valid",
]


def _norm(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _parse_location_parts(raw: str) -> tuple[str, str, str]:
    """Best-effort (city, state, country) split for a new location_info row."""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return "", "", ""
    city = parts[0]
    country = standardize_country(parts[-1]) or "" if len(parts) > 1 else ""
    state = parse_us_state_from_location_text(raw)
    return city, state, country


def build_location_lookup(location_df: pd.DataFrame) -> dict[str, str]:
    """Map raw + standardized event_location strings -> location_id.

    Rows with a non-empty location_id win; first occurrence is kept so existing
    ids stay stable across runs.
    """
    lookup: dict[str, str] = {}
    if location_df is None or location_df.empty:
        return lookup
    if "location_id" not in location_df.columns:
        return lookup

    for _, row in location_df.iterrows():
        loc_id = _norm(row.get("location_id"))
        if not loc_id:
            continue
        for col in ("event_location", "event_location_standardized"):
            key = _norm(row.get(col)).lower()
            if key and key not in lookup:
                lookup[key] = loc_id
    return lookup


def resolve_result_location_ids(
    results_df: pd.DataFrame,
    location_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fill empty results.location_id from event_location.

    Returns (results_df, location_df). New event_location values are assigned a
    fresh sequential location_id and appended to location_df so subsequent joins
    (and Tableau) resolve them.
    """
    if results_df is None or results_df.empty:
        return results_df, location_df
    if "event_location" not in results_df.columns:
        return results_df, location_df

    results_df = results_df.copy()
    if "location_id" not in results_df.columns:
        results_df["location_id"] = ""

    location_df = (
        location_df.copy()
        if location_df is not None and not location_df.empty
        else pd.DataFrame(columns=LOCATION_COLUMNS)
    )

    lookup = build_location_lookup(location_df)

    existing_ids = pd.to_numeric(
        location_df.get("location_id", pd.Series(dtype=str)), errors="coerce"
    )
    next_id = int(existing_ids.max()) + 1 if existing_ids.notna().any() else 1

    loc_raw = results_df["event_location"].map(_norm)
    loc_key = loc_raw.str.lower()
    cur_id = results_df["location_id"].map(_norm)

    needs_fill = (cur_id == "") & (loc_key != "")
    new_rows: list[dict[str, str]] = []

    resolved = cur_id.copy()
    for idx in results_df.index[needs_fill]:
        key = loc_key.at[idx]
        if key in lookup:
            resolved.at[idx] = lookup[key]
            continue
        raw = loc_raw.at[idx]
        new_id = str(next_id)
        next_id += 1
        lookup[key] = new_id
        city, state, country = _parse_location_parts(raw)
        new_rows.append(
            {
                "location_id": new_id,
                "event_city": city,
                "event_state": state,
                "event_country": country,
                "latitude": "",
                "longitude": "",
                "event_location": raw,
                "event_location_standardized": "",
                "coordinates_valid": "",
            }
        )
        resolved.at[idx] = new_id

    results_df["location_id"] = resolved

    if new_rows:
        appended = pd.DataFrame(new_rows).reindex(
            columns=location_df.columns if not location_df.empty else LOCATION_COLUMNS,
            fill_value="",
        )
        location_df = pd.concat([location_df, appended], ignore_index=True)

    return results_df, location_df

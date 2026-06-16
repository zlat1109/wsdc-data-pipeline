"""Known metadata for WSDC events missing from events_wsdc or with empty location rows."""

from __future__ import annotations

from typing import Any

import pandas as pd

# Structured location row used to patch empty location_info rows.
LocationPatch = dict[str, str]

# Events that appear in results but not in events_wsdc (no URL / typical location in DB),
# or need catalog URL updates after a rebrand.
KNOWN_EVENT_METADATA: dict[int, dict[str, Any]] = {
    229: {
        "name": "Scandinavian Open",
        "url": "http://www.snowcs.se/",
        "typical_location": "Stockholm, Sweden",
        "location": {
            "event_city": "Stockholm",
            "event_state": "",
            "event_country": "Sweden",
            "event_location": "Stockholm, Sweden",
            "event_location_standardized": "Stockholm, Sweden",
        },
    },
    324: {
        "name": "BTO Open",
        "url": "https://ctodance.ca/",
        "typical_location": "Calgary, Alberta, Canada",
    },
    380: {
        "name": "SASS Spooky Albany Swing Spectacular",
        "url": "http://www.spookyalbanyswing.com/",
        "typical_location": "Albany, NY, United States",
    },
    # Rebrand on schedule: Rocket City Swing; points catalog still "Westies on the Water".
    323: {
        "url": "http://rocketcityswing.com/",
        "typical_location": "Huntsville, Alabama, United States",
    },
}

# location_id -> location_info row fixes when WSDC export leaves rows empty
# (only when event_id-based patch is not applicable)
LOCATION_ID_CORRECTIONS: dict[int, LocationPatch] = {
    # SASS / Albany — WSDC export: event_state empty, event_location "Albany, NY, Albany"
    161: {
        "event_city": "Albany",
        "event_state": "New York",
        "event_country": "United States",
        "event_location": "Albany, NY",
        "event_location_standardized": "Albany, NY",
    },
}


def event_location_patches() -> dict[int, LocationPatch]:
    """Location patches keyed by WSDC event_id (stable; not location_id)."""
    out: dict[int, LocationPatch] = {}
    for event_id, meta in KNOWN_EVENT_METADATA.items():
        loc = meta.get("location")
        if isinstance(loc, dict) and loc:
            out[int(event_id)] = loc
    return out


def _location_row_empty(df: pd.DataFrame, mask: pd.Series) -> pd.Series:
    empty = mask.copy()
    for col in ("event_city", "event_country", "event_location"):
        if col not in df.columns:
            continue
        vals = df.loc[mask, col].astype(str).str.strip()
        empty &= vals.isna() | (vals == "") | (vals == "nan")
    return empty


def apply_event_location_patches(
    location_df: pd.DataFrame,
    results_df: pd.DataFrame | None,
) -> pd.DataFrame:
    """Fill empty location_info rows by event_id from results (not hardcoded location_id)."""
    if results_df is None or location_df.empty or "location_id" not in location_df.columns:
        return location_df

    df = location_df.copy()
    id_col = "event_name_id" if "event_name_id" in results_df.columns else None
    if not id_col:
        return df

    for event_id, fixes in event_location_patches().items():
        loc_ids = (
            results_df.loc[results_df[id_col].astype(str) == str(event_id), "location_id"]
            .dropna()
            .astype(str)
            .unique()
        )
        for loc_id in loc_ids:
            mask = df["location_id"].astype(str) == loc_id
            if not mask.any():
                continue
            target = _location_row_empty(df, mask)
            if not target.any():
                continue
            for col, val in fixes.items():
                if col in df.columns:
                    df.loc[target, col] = val
    return df

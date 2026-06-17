"""Apply knowledge-layer patches to DataFrames."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from transform.knowledge.events import (
    EVENT_LOCATION_EXACT_CORRECTIONS,
    EVENT_LOCATION_SUBSTRING_CORRECTIONS,
    EVENT_NAME_LOCATION_OVERRIDES,
    EVENT_NAME_NORMALIZATION,
    KNOWN_EVENT_METADATA,
)
from transform.knowledge.locations import LocationPatch

if TYPE_CHECKING:
    from transform.preprocess_tracker import PreprocessTracker


def event_location_patches() -> dict[int, LocationPatch]:
    """Location patches keyed by WSDC event_id (stable; not location_id)."""
    out: dict[int, LocationPatch] = {}
    for event_id, meta in KNOWN_EVENT_METADATA.items():
        loc = meta.get('location')
        if isinstance(loc, dict) and loc:
            out[int(event_id)] = loc
    return out


def _location_row_empty(df: pd.DataFrame, mask: pd.Series) -> pd.Series:
    empty = mask.copy()
    for col in ('event_city', 'event_country', 'event_location'):
        if col not in df.columns:
            continue
        vals = df.loc[mask, col].astype(str).str.strip()
        empty &= vals.isna() | (vals == '') | (vals == 'nan')
    return empty


def apply_event_location_patches(
    location_df: pd.DataFrame,
    results_df: pd.DataFrame | None,
) -> pd.DataFrame:
    """Fill empty location_info rows by event_id from results (not hardcoded location_id)."""
    if results_df is None or location_df.empty or 'location_id' not in location_df.columns:
        return location_df

    df = location_df.copy()
    id_col = 'event_name_id' if 'event_name_id' in results_df.columns else None
    if not id_col:
        return df

    for event_id, fixes in event_location_patches().items():
        loc_ids = (
            results_df.loc[results_df[id_col].astype(str) == str(event_id), 'location_id']
            .dropna()
            .astype(str)
            .unique()
        )
        for loc_id in loc_ids:
            mask = df['location_id'].astype(str) == loc_id
            if not mask.any():
                continue
            target = _location_row_empty(df, mask)
            if not target.any():
                continue
            for col, val in fixes.items():
                if col in df.columns:
                    df.loc[target, col] = val
    return df


def apply_event_corrections(df: pd.DataFrame) -> pd.DataFrame:
    """Apply manual event name and location corrections to results."""
    df = df.copy()

    if 'event_name' in df.columns:
        df['event_name'] = df['event_name'].replace(EVENT_NAME_NORMALIZATION)
        if 'event_location' in df.columns:
            for name, location in EVENT_NAME_LOCATION_OVERRIDES.items():
                mask = df['event_name'] == name
                if mask.any():
                    df.loc[mask, 'event_location'] = location

    if 'event_location' in df.columns:
        df['event_location'] = df['event_location'].replace(EVENT_LOCATION_EXACT_CORRECTIONS)
        for old, new in EVENT_LOCATION_SUBSTRING_CORRECTIONS:
            df['event_location'] = df['event_location'].str.replace(old, new, regex=False)

    return df

"""Apply knowledge-layer patches to DataFrames."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from transform.geography.resolve import (
    _canonical_location_raw,
    build_location_lookup,
    location_lookup_key_from_text,
)
from transform.geography.utils import norm_value
from transform.knowledge.events import (
    EVENT_LOCATION_EXACT_CORRECTIONS,
    EVENT_LOCATION_SUBSTRING_CORRECTIONS,
    EVENT_NAME_LOCATION_OVERRIDES,
    EVENT_NAME_NORMALIZATION,
    EVENT_NAME_YEAR_LOCATION_OVERRIDES,
    KNOWN_EVENT_METADATA,
)
from transform.knowledge.locations import LocationPatch

if TYPE_CHECKING:
    from transform.preprocess_tracker import PreprocessTracker

logger = logging.getLogger(__name__)

# Module-level alias so call sites read naturally.
_norm = norm_value


def _result_event_years(df: pd.DataFrame) -> pd.Series:
    """Numeric event year for year-scoped location overrides."""
    if "event_year" in df.columns:
        return pd.to_numeric(df["event_year"], errors="coerce")
    return pd.Series(pd.NA, index=df.index, dtype="Float64")


def _apply_location_target(
    df: pd.DataFrame,
    mask: pd.Series,
    target_location: str,
    lookup: dict,
    *,
    event_label: str,
) -> int:
    """Set event_location + location_id for masked rows; return count changed."""
    raw = _canonical_location_raw(_norm(target_location))
    key = location_lookup_key_from_text(raw)
    loc_id = lookup.get(key) or lookup.get(raw.lower())
    if not loc_id:
        logger.warning(
            "force_result_locations_from_event_name_overrides: target location %r "
            "(key=%r) for event %r not found in location_info — override skipped. "
            "Add this city to location_info or check EVENT_NAME_*_LOCATION_OVERRIDES.",
            target_location,
            key,
            event_label,
        )
        return 0

    before_loc = df.loc[mask, "location_id"].map(_norm)
    before_text = df.loc[mask, "event_location"].map(_norm)
    need = (before_loc != str(loc_id)) | (before_text != raw)
    n = int(need.sum())
    if not n:
        return 0

    apply_mask = mask & need
    df.loc[apply_mask, "event_location"] = raw
    df.loc[apply_mask, "location_id"] = str(loc_id)
    return n


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


def backfill_empty_result_event_locations(results_df: pd.DataFrame) -> pd.DataFrame:
    """Fill empty results.event_location from catalog metadata.

    WSDC lookup often omits event.location (e.g. Scandinavian Open / event_id 229).
    resolve_result_location_ids needs event_location text; this backfill runs first.
    """
    if results_df is None or results_df.empty:
        return results_df

    df = results_df.copy()
    if "event_location" not in df.columns:
        df["event_location"] = ""

    empty = df["event_location"].map(norm_value) == ""

    if "event_name_id" in df.columns:
        for event_id, meta in KNOWN_EVENT_METADATA.items():
            loc = meta.get("location")
            if isinstance(loc, dict) and loc.get("event_location"):
                event_loc = norm_value(loc["event_location"])
            else:
                event_loc = norm_value(meta.get("typical_location"))
            if not event_loc:
                continue
            mask = empty & (df["event_name_id"].astype(str).str.strip() == str(event_id))
            if mask.any():
                df.loc[mask, "event_location"] = event_loc
                empty = df["event_location"].map(norm_value) == ""

    if "event_name" in df.columns:
        for event_id, meta in KNOWN_EVENT_METADATA.items():
            name = norm_value(meta.get("name"))
            if not name:
                continue
            loc = meta.get("location")
            if isinstance(loc, dict) and loc.get("event_location"):
                event_loc = norm_value(loc["event_location"])
            else:
                event_loc = norm_value(meta.get("typical_location"))
            if not event_loc:
                continue
            mask = empty & (df["event_name"].astype(str).str.strip() == name)
            if mask.any():
                df.loc[mask, "event_location"] = event_loc
                empty = df["event_location"].map(norm_value) == ""

    if "event_name" in df.columns:
        for name, location in EVENT_NAME_LOCATION_OVERRIDES.items():
            mask = empty & (df["event_name"].astype(str).str.strip() == name)
            if mask.any():
                df.loc[mask, "event_location"] = location
                empty = df["event_location"].map(norm_value) == ""

        years = _result_event_years(df)
        for (name, y0, y1), location in EVENT_NAME_YEAR_LOCATION_OVERRIDES.items():
            mask = (
                empty
                & (df["event_name"].astype(str).str.strip() == name)
                & years.notna()
                & (years >= y0)
                & (years <= y1)
            )
            if mask.any():
                df.loc[mask, "event_location"] = location
                empty = df["event_location"].map(norm_value) == ""

    return df


def force_result_locations_from_event_name_overrides(
    results_df: pd.DataFrame,
    location_df: pd.DataFrame,
) -> tuple[pd.DataFrame, int]:
    """Force event_location + location_id for name (and year) location overrides.

    WSDC sometimes reuses a wrong location_id across unrelated events (e.g. Sweden
    Westie Gala rows tagged as Wailea / Aloha Open). Text overrides alone do not
    fix joins: resolve_result_location_ids only fills *empty* location_id values.

    Year-scoped overrides run after flat ones so relocating series (Sunny Side,
    Go West) keep distinct cities per KEEP_SEPARATE event_id.
    """
    if results_df is None or results_df.empty or "event_name" not in results_df.columns:
        return results_df, 0
    if location_df is None or location_df.empty:
        return results_df, 0

    df = results_df.copy()
    if "location_id" not in df.columns:
        df["location_id"] = ""
    if "event_location" not in df.columns:
        df["event_location"] = ""

    lookup = build_location_lookup(location_df)
    changed = 0

    for event_name, target_location in EVENT_NAME_LOCATION_OVERRIDES.items():
        mask = df["event_name"].astype(str).str.strip() == event_name
        if not mask.any():
            continue
        changed += _apply_location_target(
            df, mask, target_location, lookup, event_label=event_name
        )

    years = _result_event_years(df)
    year_names = {name for name, _y0, _y1 in EVENT_NAME_YEAR_LOCATION_OVERRIDES}
    for event_name in sorted(year_names):
        name_mask = df["event_name"].astype(str).str.strip() == event_name
        missing_year = name_mask & years.isna()
        n_missing = int(missing_year.sum())
        if n_missing:
            logger.warning(
                "force_result_locations_from_event_name_overrides: %s row(s) named %r "
                "have null event_year — year-scoped location override skipped",
                n_missing,
                event_name,
            )

    for (event_name, y0, y1), target_location in EVENT_NAME_YEAR_LOCATION_OVERRIDES.items():
        mask = (
            (df["event_name"].astype(str).str.strip() == event_name)
            & years.notna()
            & (years >= y0)
            & (years <= y1)
        )
        if not mask.any():
            continue
        changed += _apply_location_target(
            df,
            mask,
            target_location,
            lookup,
            event_label=f"{event_name} [{y0}-{y1}]",
        )

    return df, changed


def force_events_wsdc_locations_from_event_name_overrides(
    events_df: pd.DataFrame,
    *,
    name_col: str = "name",
    location_col: str = "location",
) -> tuple[pd.DataFrame, int]:
    """Force events_wsdc.location text from name (and year) location overrides.

    Results get location_id remaps in force_result_locations_*; the WSDC scrape
    table only has a free-text location and was previously left on shared-wrong
    strings (e.g. Dance Jam → Jeju), which then polluted export/catalog views.
    """
    if events_df is None or events_df.empty:
        return events_df, 0
    if name_col not in events_df.columns or location_col not in events_df.columns:
        return events_df, 0

    df = events_df.copy()
    changed = 0

    def _apply_text(mask: pd.Series, target_location: str) -> int:
        nonlocal changed
        if not mask.any():
            return 0
        raw = _canonical_location_raw(_norm(target_location))
        before = df.loc[mask, location_col].map(_norm)
        need = before != raw
        n = int(need.sum())
        if not n:
            return 0
        df.loc[mask & need, location_col] = raw
        changed += n
        return n

    for event_name, target_location in EVENT_NAME_LOCATION_OVERRIDES.items():
        _apply_text(df[name_col].astype(str).str.strip() == event_name, target_location)

    years = _result_event_years(df)
    # events_wsdc uses `year` in some exports; prefer event_year then year.
    if years.isna().all() and "year" in df.columns:
        years = pd.to_numeric(df["year"], errors="coerce")
    for (event_name, y0, y1), target_location in EVENT_NAME_YEAR_LOCATION_OVERRIDES.items():
        mask = (
            (df[name_col].astype(str).str.strip() == event_name)
            & years.notna()
            & (years >= y0)
            & (years <= y1)
        )
        _apply_text(mask, target_location)

    return df, changed


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

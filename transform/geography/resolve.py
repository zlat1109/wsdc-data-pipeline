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

from transform.geography.city import format_event_location, normalize_location_whitespace
from transform.geography.constants import STATE_CODE_TO_NAME
from transform.geography.normalize import (
    parse_us_state_from_location_text,
    standardize_country,
)
from transform.knowledge.locations import (
    LOCATION_ID_MERGE_MAP,
    LOCATION_RAW_ALIASES,
    LOCATION_STRING_ALIASES,
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


def _canonical_location_raw(raw: str) -> str:
    """Map known WSDC location typos before lookup key generation."""
    normalized = normalize_location_whitespace(_norm(raw))
    return LOCATION_RAW_ALIASES.get(normalized, normalized)


def location_lookup_key_from_text(raw: str) -> str:
    """Canonical lowercase key for matching event_location strings."""
    raw = _canonical_location_raw(raw)
    if not raw:
        return ""

    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return raw.lower()

    city = parts[0]
    country = ""
    state = ""

    if len(parts) >= 3:
        state = parts[1]
        country = standardize_country(parts[-1]) or parts[-1]
    elif len(parts) == 2:
        second = parts[1]
        std_second = standardize_country(second) or second
        parsed_state = parse_us_state_from_location_text(raw)
        if std_second in {"United States", "USA", "US"} or parsed_state:
            state = parsed_state or second
            country = "United States"
        else:
            country = std_second

    row = pd.Series(
        {
            "event_city": city,
            "event_state": state,
            "event_country": country,
            "event_location": raw,
        }
    )
    formatted = format_event_location(row).lower()
    if country == "United Kingdom" and city:
        return f"{city.lower()}, united kingdom"
    return formatted


def location_lookup_key_from_row(row: pd.Series) -> str:
    """Canonical lookup key for a location_info row."""
    city = _norm(row.get("event_city"))
    if city:
        key = location_lookup_key_from_text(format_event_location(row))
        if key:
            return key
    for col in ("event_location_standardized", "event_location"):
        text = _norm(row.get(col))
        if text:
            key = location_lookup_key_from_text(text)
            if key:
                return key
    return ""


def _register_lookup_keys(lookup: dict[str, str], row: pd.Series, loc_id: str) -> None:
    for col in ("event_location", "event_location_standardized"):
        key = _norm(row.get(col)).lower()
        if key:
            lookup.setdefault(key, loc_id)
    canon = location_lookup_key_from_row(row)
    if canon:
        lookup.setdefault(canon, loc_id)


def _parse_location_parts(raw: str) -> tuple[str, str, str]:
    """Best-effort (city, state, country) split for a new location_info row."""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return "", "", ""
    city = parts[0]
    if len(parts) == 2:
        # WSDC often emits "Atlanta, GA USA" (state + country without comma).
        tokens = parts[1].split()
        if len(tokens) >= 2 and tokens[-1].upper() in {"USA", "US", "U.S.", "U.S.A."}:
            state_code = tokens[0].upper()
            state = STATE_CODE_TO_NAME.get(state_code, "") if len(state_code) == 2 else ""
            if not state:
                state = parse_us_state_from_location_text(raw)
            return city, state, "United States"
    country = standardize_country(parts[-1]) or "" if len(parts) > 1 else ""
    state = parse_us_state_from_location_text(raw)
    return city, state, country


def build_location_lookup(location_df: pd.DataFrame) -> dict[str, str]:
    """Map raw + standardized event_location strings -> location_id.

    Rows with a non-empty location_id win; first occurrence is kept so existing
    ids stay stable across runs.
    """
    lookup: dict[str, str] = {}
    if location_df is not None and not location_df.empty and "location_id" in location_df.columns:
        for _, row in location_df.iterrows():
            loc_id = _norm(row.get("location_id"))
            if not loc_id:
                continue
            _register_lookup_keys(lookup, row, loc_id)
    for key, loc_id in LOCATION_STRING_ALIASES.items():
        lookup.setdefault(key, loc_id)
    return lookup


def consolidate_location_ids(
    results_df: pd.DataFrame,
    location_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Remap duplicate location_id rows to canonical ids and drop merged location_info rows."""
    if results_df is None or results_df.empty:
        return results_df, location_df
    if not LOCATION_ID_MERGE_MAP:
        return results_df, location_df

    results_df = results_df.copy()
    if "location_id" in results_df.columns:
        loc_col = results_df["location_id"].astype(str).str.strip()
        for old_id, new_id in LOCATION_ID_MERGE_MAP.items():
            results_df.loc[loc_col == old_id, "location_id"] = new_id

    if location_df is None or location_df.empty or "location_id" not in location_df.columns:
        return results_df, location_df

    location_df = location_df.copy()
    drop_ids = set(LOCATION_ID_MERGE_MAP.keys())
    keep = ~location_df["location_id"].astype(str).str.strip().isin(drop_ids)
    location_df = location_df.loc[keep].reset_index(drop=True)
    return results_df, location_df


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
    result_ids = pd.to_numeric(
        results_df.get("location_id", pd.Series(dtype=str)), errors="coerce"
    )
    # Never restart the id space at 1 when results already carry location_ids
    # (empty/partial location_info would otherwise collide with historical FKs).
    max_from_loc = int(existing_ids.max()) if existing_ids.notna().any() else 0
    max_from_res = int(result_ids.max()) if result_ids.notna().any() else 0
    next_id = max(max_from_loc, max_from_res, 0) + 1

    loc_raw = results_df["event_location"].map(_norm)
    cur_id = results_df["location_id"].map(_norm)

    needs_fill = (cur_id == "") & (loc_raw != "")
    if needs_fill.any() and location_df.empty and result_ids.notna().any() and int((result_ids > 0).sum()) > 0:
        raise RuntimeError(
            "location_info is empty but dancers_results_info already has "
            "location_id values; refusing to invent location rows without a "
            "registry. Restore location_info.csv (or export.location_info) "
            "before resolve."
        )
    new_rows: list[dict[str, str]] = []

    resolved = cur_id.copy()
    for idx in results_df.index[needs_fill]:
        raw = _canonical_location_raw(loc_raw.at[idx])
        key = location_lookup_key_from_text(raw)
        if key in lookup:
            resolved.at[idx] = lookup[key]
            continue
        raw_lower = raw.lower()
        if raw_lower in lookup:
            resolved.at[idx] = lookup[raw_lower]
            continue
        new_id = str(next_id)
        next_id += 1
        if key:
            lookup[key] = new_id
        lookup[raw_lower] = new_id
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


def dedupe_location_info(
    results_df: pd.DataFrame,
    location_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Merge location_info rows that share a canonical lookup key; remap results."""
    if location_df is None or location_df.empty or "location_id" not in location_df.columns:
        return results_df, location_df, 0

    location_df = location_df.copy()
    results_df = results_df.copy() if results_df is not None else pd.DataFrame()
    location_df["_lookup_key"] = location_df.apply(location_lookup_key_from_row, axis=1)

    id_remap: dict[str, str] = {}
    keep_indices: list[int] = []

    for key, grp in location_df.groupby("_lookup_key", sort=False):
        if not key:
            keep_indices.extend(grp.index.tolist())
            continue

        ids = pd.to_numeric(grp["location_id"], errors="coerce").dropna()
        if ids.empty:
            keep_indices.extend(grp.index.tolist())
            continue

        canonical = str(int(ids.min()))
        for old_id in grp["location_id"].astype(str).str.strip():
            if old_id and old_id != canonical:
                id_remap[old_id] = canonical

        canonical_rows = grp[grp["location_id"].astype(str).str.strip() == canonical]
        keep_indices.append(
            int(canonical_rows.index[0]) if len(canonical_rows) else int(grp.index[0])
        )

    merged_rows = len(location_df) - len(keep_indices)
    location_df = (
        location_df.loc[sorted(set(keep_indices))]
        .drop(columns=["_lookup_key"])
        .reset_index(drop=True)
    )

    if id_remap and not results_df.empty and "location_id" in results_df.columns:
        loc_col = results_df["location_id"].astype(str).str.strip()
        for old_id, new_id in id_remap.items():
            results_df.loc[loc_col == old_id, "location_id"] = new_id

    return results_df, location_df, merged_rows

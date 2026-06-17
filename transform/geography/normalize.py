"""Geography normalization for location_info."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import pandas as pd

from transform.geography.canonical import canonicalize_city_coordinates
from transform.geography.constants import (
    CANADA_PROVINCES,
    COUNTRY_STANDARDIZATION,
    STATE_CODE_TO_NAME,
    STATE_NAME_TO_CODE,
    UK_REGIONS,
)
from transform.knowledge.locations import (
    LOCATION_ID_CORRECTIONS as LOCATION_INFO_ID_CORRECTIONS,
    LOCATION_INFO_CITY_CORRECTIONS,
)

if TYPE_CHECKING:
    from transform.preprocess_tracker import PreprocessTracker


def standardize_country(country: str) -> Optional[str]:
    if pd.isna(country) or country == '':
        return None
    country_str = str(country).strip()
    return COUNTRY_STANDARDIZATION.get(country_str, country_str)


def standardize_location(row: pd.Series) -> str:
    city = str(row.get('event_city', '')).strip()
    state = str(row.get('event_state', '')).strip() if pd.notna(row.get('event_state')) else ''
    country = str(row.get('event_country', '')).strip() if pd.notna(row.get('event_country')) else ''

    if country == 'United States' and state:
        state_code = STATE_NAME_TO_CODE.get(state, state)
        return f"{city}, {state_code}"
    if country:
        return f"{city}, {country}"
    return city


def parse_us_state_from_location_text(location: str) -> str:
    if not location or not str(location).strip():
        return ''

    parts = [part.strip() for part in str(location).split(',') if part.strip()]
    if len(parts) < 2:
        return ''

    second = parts[1]
    if len(second) == 2 and second.isalpha():
        return STATE_CODE_TO_NAME.get(second.upper(), '')

    for part in parts[1:]:
        if part in STATE_NAME_TO_CODE:
            return part
        if part.upper() in {'USA', 'US', 'UNITED STATES'}:
            continue

    return ''


def fill_us_state_from_location(row: pd.Series) -> str:
    if pd.notna(row.get('event_state')) and str(row.get('event_state')).strip():
        return str(row.get('event_state')).strip()

    country = str(row.get('event_country', '')).strip() if pd.notna(row.get('event_country')) else ''
    if country not in {'United States', 'USA', 'US'}:
        return ''

    location = str(row.get('event_location', '')).strip() if pd.notna(row.get('event_location')) else ''
    return parse_us_state_from_location_text(location)


def fill_international_state(row: pd.Series) -> str:
    if pd.notna(row.get('event_state')) and str(row.get('event_state')).strip():
        return str(row.get('event_state')).strip()

    country = str(row.get('event_country', '')).strip() if pd.notna(row.get('event_country')) else ''
    city = str(row.get('event_city', '')).strip() if pd.notna(row.get('event_city')) else ''

    if country == 'Canada':
        return CANADA_PROVINCES.get(city, '')
    if country == 'United Kingdom':
        return UK_REGIONS.get(city, '')
    return ''


def validate_coordinates(row: pd.Series) -> bool:
    lat = row.get('latitude')
    lon = row.get('longitude')

    if pd.isna(lat) or pd.isna(lon):
        return False

    try:
        lat_float = float(lat)
        lon_float = float(lon)
        return -90 <= lat_float <= 90 and -180 <= lon_float <= 180
    except (ValueError, TypeError):
        return False


def _apply_id_corrections(
    df: pd.DataFrame,
    tracker: PreprocessTracker | None,
) -> pd.DataFrame:
    if 'location_id' not in df.columns:
        return df

    table = 'location_info'
    for loc_id, fixes in LOCATION_INFO_ID_CORRECTIONS.items():
        mask = df['location_id'].astype(str) == str(loc_id)
        if not mask.any():
            continue

        empty_mask = mask.copy()
        for key_col in ['event_city', 'event_country', 'event_location']:
            if key_col in df.columns and key_col in fixes:
                col_vals = df.loc[mask, key_col].astype(str).str.strip()
                empty_mask &= col_vals.isna() | (col_vals == '') | (col_vals == 'nan')

        target_mask = empty_mask if empty_mask.any() else mask
        for col, val in fixes.items():
            if col in df.columns and target_mask.any():
                if tracker is not None:
                    before = df.loc[target_mask, col].astype(str).iloc[0]
                    tracker.record(
                        'LOCATION_INFO_ID_CORRECTION',
                        table,
                        col,
                        f'location_id={loc_id} was {before}',
                        str(val),
                        int(target_mask.sum()),
                        'location_id_fix',
                    )
                df.loc[target_mask, col] = val
    return df


def _apply_city_corrections(
    df: pd.DataFrame,
    tracker: PreprocessTracker | None,
) -> pd.DataFrame:
    if 'event_city' not in df.columns:
        return df

    table = 'location_info'
    city_col = df['event_city'].fillna('').astype(str).str.strip()
    for city_key, fixes in LOCATION_INFO_CITY_CORRECTIONS.items():
        mask = city_col.str.lower() == city_key
        if not mask.any():
            continue
        for col, val in fixes.items():
            if col in df.columns:
                if tracker is not None:
                    tracker.record(
                        'LOCATION_INFO_CITY_CORRECTION',
                        table,
                        col,
                        f'city={city_key}',
                        str(val),
                        int(mask.sum()),
                        'city_fix',
                    )
                df.loc[mask, col] = val
    return df


def _apply_canonical_coordinates(
    df: pd.DataFrame,
    tracker: PreprocessTracker | None,
) -> pd.DataFrame:
    if 'latitude' not in df.columns or 'longitude' not in df.columns:
        return df

    before_lat = df['latitude'].astype(str)
    before_lon = df['longitude'].astype(str)
    out = canonicalize_city_coordinates(df)

    if tracker is not None:
        changed = (before_lat != out['latitude'].astype(str)) | (
            before_lon != out['longitude'].astype(str)
        )
        count = int(changed.sum())
        if count:
            tracker.record(
                'CITY_CANONICAL_COORDINATES',
                'location_info',
                'latitude/longitude',
                'suburb/venue coords',
                'city center',
                count,
                'canonical_coords',
            )
    return out


def normalize_geography(
    df: pd.DataFrame,
    tracker: PreprocessTracker | None = None,
) -> pd.DataFrame:
    """Apply all location_info geography normalizations."""
    df = df.copy()
    df = _apply_id_corrections(df, tracker)
    df = _apply_city_corrections(df, tracker)

    if 'event_country' in df.columns:
        df['event_country'] = df['event_country'].apply(standardize_country)

    if 'event_state' in df.columns:
        missing_state = df['event_state'].fillna('').astype(str).str.strip() == ''
        if missing_state.any():
            df.loc[missing_state, 'event_state'] = df.loc[missing_state].apply(
                fill_us_state_from_location
            )
        df['event_state'] = df.apply(fill_international_state, axis=1)

    df = _apply_canonical_coordinates(df, tracker)

    if 'event_location' in df.columns:
        df['event_location_standardized'] = df.apply(standardize_location, axis=1)

    if 'latitude' in df.columns and 'longitude' in df.columns:
        df['coordinates_valid'] = df.apply(validate_coordinates, axis=1)

    return df

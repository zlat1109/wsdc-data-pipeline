"""Canonical city-level coordinates for map dashboards."""

from __future__ import annotations

from typing import Dict, Tuple

import pandas as pd

# Пригороды/площадки → центр города. Ключ: (event_city, event_country, event_state или '').
# Для США одинаковые названия в разных штатах (Burlington MA vs VT) различаются по state.
CITY_CANONICAL_COORDINATES: Dict[Tuple[str, str, str], Tuple[float, float]] = {
    ('London', 'United Kingdom', ''): (51.5072178, -0.1275862),
    ('Moscow', 'Russia', ''): (55.7568721, 37.6150527),
    ('Budapest', 'Hungary', ''): (47.497912, 19.040235),
    ('Düsseldorf', 'Germany', ''): (51.2230411, 6.7824545),
    ('Washington', 'United States', 'District of Columbia'): (38.9072873, -77.0369274),
}


def location_city_key(row: pd.Series) -> Tuple[str, str, str]:
    """Grouping key for city-level geography (US disambiguated by state)."""
    city = str(row.get('event_city', '')).strip()
    country = str(row.get('event_country', '')).strip()
    state = str(row.get('event_state', '')).strip()
    if country == 'United States' and state:
        return (city, country, state)
    return (city, country, '')


def canonicalize_city_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Align lat/lon within the same city so map markers do not split suburbs/venues."""
    if 'latitude' not in df.columns or 'longitude' not in df.columns:
        return df

    df = df.copy()
    for key, (lat, lon) in CITY_CANONICAL_COORDINATES.items():
        city, country, state = key
        city_mask = df['event_city'].fillna('').astype(str).str.strip() == city
        country_mask = df['event_country'].fillna('').astype(str).str.strip() == country
        mask = city_mask & country_mask
        if state:
            mask &= df['event_state'].fillna('').astype(str).str.strip() == state
        if mask.any():
            if pd.api.types.is_string_dtype(df['latitude']):
                df.loc[mask, 'latitude'] = str(lat)
                df.loc[mask, 'longitude'] = str(lon)
            else:
                df.loc[mask, 'latitude'] = lat
                df.loc[mask, 'longitude'] = lon
    return df

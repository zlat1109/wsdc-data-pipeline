"""Location correction maps for location_info."""

from __future__ import annotations

LocationPatch = dict[str, str]

LOCATION_ID_CORRECTIONS: dict[int, LocationPatch] = {
    161: {
        'event_city': 'Albany',
        'event_state': 'New York',
        'event_country': 'United States',
        'event_location': 'Albany, NY',
        'event_location_standardized': 'Albany, NY',
    },
}

LOCATION_INFO_CITY_CORRECTIONS = {
    'new york': {
        'event_city': 'New York',
        'event_state': 'New York',
        'event_country': 'United States',
        'event_location': 'New York, NY',
        'event_location_standardized': 'New York, NY',
    },
    'san antonio': {
        'event_city': 'San Antonio',
        'event_state': 'Texas',
        'event_country': 'United States',
        'event_location': 'San Antonio, TX',
        'event_location_standardized': 'San Antonio, TX',
    },
    'albany': {
        'event_city': 'Albany',
        'event_state': 'New York',
        'event_country': 'United States',
        'event_location': 'Albany, NY',
        'event_location_standardized': 'Albany, NY',
    },
    'burbank': {
        'event_city': 'Burbank',
        'event_state': 'California',
        'event_country': 'United States',
        'event_location': 'Burbank, CA, United States',
        'event_location_standardized': 'Burbank, CA',
    },
}

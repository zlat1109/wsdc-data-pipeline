"""Location correction maps for location_info."""

from __future__ import annotations

LocationPatch = dict[str, str]

LOCATION_ID_CORRECTIONS: dict[int, LocationPatch] = {
    25: {
        'event_city': 'Atlanta',
        'event_state': 'Georgia',
        'event_country': 'United States',
        'event_location': 'Atlanta, GA, United States',
        'event_location_standardized': 'Atlanta, GA, United States',
    },
    159: {
        'event_city': 'Singapore',
        'event_state': '',
        'event_country': 'Singapore',
        'event_location': 'Singapore, Singapore',
        'event_location_standardized': 'Singapore, Singapore',
    },
    244: {
        'event_city': 'Singapore',
        'event_state': '',
        'event_country': 'Singapore',
        'event_location': 'Singapore, Singapore',
        'event_location_standardized': 'Singapore, Singapore',
    },
    231: {
        'event_city': 'Stockholm',
        'event_state': '',
        'event_country': 'Sweden',
        'event_location': 'Stockholm, Sweden',
        'event_location_standardized': 'Stockholm, Sweden',
        'latitude': '59.3251172',
        'longitude': '18.0710935',
    },
    161: {
        'event_city': 'Albany',
        'event_state': 'New York',
        'event_country': 'United States',
        'event_location': 'Albany, NY',
        'event_location_standardized': 'Albany, NY',
    },
    191: {
        'event_city': 'Amsterdam',
        'event_state': 'North Holland',
        'event_country': 'Netherlands',
        'event_location': 'Amsterdam, North Holland, Netherlands',
        'event_location_standardized': 'Amsterdam, North Holland, Netherlands',
    },
    227: {
        'event_city': 'Venray',
        'event_state': 'Limburg',
        'event_country': 'Netherlands',
        'event_location': 'Venray, Limburg, Netherlands',
        'event_location_standardized': 'Venray, Limburg, Netherlands',
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

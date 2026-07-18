"""Event name/location correction maps and catalog metadata."""

from __future__ import annotations

from typing import Any

from transform.knowledge.event_aliases import (
    EVENT_NAME_VARIANT_TO_CATALOG,
    RESULT_TO_CATALOG_EVENT_NAME,
    build_event_name_normalization,
)
from transform.knowledge.locations import LOCATION_RAW_ALIASES

EVENT_NAME_NORMALIZATION = build_event_name_normalization()

# Force-correct WSDC rows where event_name is tied to the wrong place/location_id.
# Text alone is not enough: resolve_result_location_ids only fills *empty* ids, so
# preprocess also remaps location_id from these targets (see apply.py).
EVENT_NAME_LOCATION_OVERRIDES = {
    'Go West Swing Fest': 'Fremantle, Australia',
    'BeeMAD': 'Madrid, Spain',
    # Shared Wailea (124 / Aloha Open) wrongly applied to Swedish events.
    'Sweden Westie Gala': 'Stockholm, Sweden',
    'Swedish Swing Summer Camp': 'Stockholm, Sweden',
    # Shared St. Petersburg (222) wrongly applied to Toronto Open.
    'Toronto Open Swing & Hustle Championships': 'Toronto, Canada',
    # Calendar/site say Toulouse; results pointed at Düsseldorf (127).
    'Westie Pink City': 'Toulouse, France',
    # Calendar/site say Dundalk; results pointed at San Antonio (167).
    'Trinity Swing': 'Dundalk, Ireland',
    # Calendar/site say Providence RI; results pointed at Brno (266).
    'Northeast Swing Classic': 'Providence, RI, United States',
    # Calendar/site say Sofia; results pointed at Perth (253).
    'Grand Party Sofia (GPS)': 'Sofia, Bulgaria',
    # Site/WSDC calendar say Annecy; results pointed at Washington DC (13).
    'FRENCH CONNECTION WCS': 'Annecy, France',
    # Shared Phoenix (3 / Desert City etc.) wrongly applied to Baltic Swing (Gdańsk).
    'Baltic Swing': 'Gdańsk, Poland',
}

EVENT_LOCATION_EXACT_CORRECTIONS = {
    'Adelaide, South Australia, Australia': 'Adelaide, Australia',
    'Budapest': 'Budapest, Hungary',
    'Calgar Yy, Alberta': 'Calgary, Canada',
    'Czech Republic': 'Brno, Czech Republic',
    'Dallas, Texas': 'Dallas, TX',
    'East Rutherford': 'East Rutherford, NJ',
    'Edmonton, ON': 'Edmonton, Canada',
    'Gold Coast, Queensland': 'Gold Coast, Australia',
    'Israel': 'Tel Aviv, Israel',
    'Ottawa': 'Ottawa, Canada',
    'Paris': 'Paris, France',
    'Sweden': 'Stockholm, Sweden',
    'Toulouse': 'Toulouse, France',
    'Redmond, Oregon': 'Redmond, OR',
    'Seoul, South Korea': 'Seoul, Republic of Korea',
    'Seoul, Korea': 'Seoul, Republic of Korea',
    'Jeju, South Korea': 'Jeju, Republic of Korea',
    'Incheon, South Korea': 'Incheon, Republic of Korea',
    'South Korea': 'Republic of Korea',
    'Concord CA': 'Concord, CA',
    'St. Burlatskaya, Russia': 'Samara, Russia',
    'CHICAGO, IL, United States': 'Chicago, IL, United States',
    'Atlanta, GA USA': 'Atlanta, GA, United States',
    'St. Louis, Mo, USA': 'St. Louis, MO, USA',
    'PARIS, France': 'Paris, France',
    'Moscow,  Russia': 'Moscow, Russia',
    'Stockholm,  Sweden': 'Stockholm, Sweden',
    'Singapore': 'Singapore, Singapore',
    'Singapore, Singapore, Singapore': 'Singapore, Singapore',
    'New York': 'New York, NY',
    **LOCATION_RAW_ALIASES,
}

EVENT_LOCATION_SUBSTRING_CORRECTIONS = [
    ('Scotland', 'United Kingdom'),
    ('ENGLAND', 'United Kingdom'),
    ('England', 'United Kingdom'),
    ('UK', 'United Kingdom'),
    ('FRANCE', 'France'),
    ('QC Canada', 'Canada'),
    ('QC', 'Canada'),
    ('Isreal', 'Israel'),
    ('Washington Dc', 'Washington'),
    ('Kindom', 'Kingdom'),
    ('Italia', 'Italy'),
    ('BC', 'Canada'),
    ('Bernadino', 'Bernardino'),
    ('Minn / St. Paul', 'St. Paul'),
]

KNOWN_EVENT_METADATA: dict[int, dict[str, Any]] = {
    229: {
        'name': 'Scandinavian Open',
        'url': 'http://www.snowcs.se/',
        'typical_location': 'Stockholm, Sweden',
        'location': {
            'event_city': 'Stockholm',
            'event_state': '',
            'event_country': 'Sweden',
            'event_location': 'Stockholm, Sweden',
            'event_location_standardized': 'Stockholm, Sweden',
        },
    },
    222: {
        'name': 'Baltic Swing',
        'url': 'http://www.balticswing.com',
        'typical_location': 'Gdańsk, Poland',
        'location': {
            'event_city': 'Gdańsk',
            'event_state': '',
            'event_country': 'Poland',
            'event_location': 'Gdańsk, Poland',
            'event_location_standardized': 'Gdańsk, Poland',
        },
    },
    240: {
        'name': 'Sweden Westie Gala',
        'url': 'http://www.westiegala.com/',
        'typical_location': 'Stockholm, Sweden',
        'location': {
            'event_city': 'Stockholm',
            'event_state': '',
            'event_country': 'Sweden',
            'event_location': 'Stockholm, Sweden',
            'event_location_standardized': 'Stockholm, Sweden',
        },
    },
    264: {
        'name': 'Swedish Swing Summer Camp',
        'url': 'http://www.uptownswing.se/',
        'typical_location': 'Stockholm, Sweden',
        'location': {
            'event_city': 'Stockholm',
            'event_state': '',
            'event_country': 'Sweden',
            'event_location': 'Stockholm, Sweden',
            'event_location_standardized': 'Stockholm, Sweden',
        },
    },
    147: {
        'name': 'Toronto Open Swing & Hustle Championships',
        'url': 'http://www.TOSHC.com',
        'typical_location': 'Toronto, Canada',
        'location': {
            'event_city': 'Toronto',
            'event_state': '',
            'event_country': 'Canada',
            'event_location': 'Toronto, Canada',
            'event_location_standardized': 'Toronto, Canada',
        },
    },
    312: {
        'name': 'Westie Pink City',
        'url': 'http://www.westiepinkcity.fr/',
        'typical_location': 'Toulouse, France',
        'location': {
            'event_city': 'Toulouse',
            'event_state': '',
            'event_country': 'France',
            'event_location': 'Toulouse, France',
            'event_location_standardized': 'Toulouse, France',
        },
    },
    363: {
        'name': 'Trinity Swing',
        'url': 'http://www.trinityswing.com/',
        'typical_location': 'Dundalk, Ireland',
        'location': {
            'event_city': 'Dundalk',
            'event_state': '',
            'event_country': 'Ireland',
            'event_location': 'Dundalk, Ireland',
            'event_location_standardized': 'Dundalk, Ireland',
        },
    },
    376: {
        'name': 'Northeast Swing Classic',
        'url': 'http://www.northeastswingclassic.com/',
        'typical_location': 'Providence, RI, United States',
        'location': {
            'event_city': 'Providence',
            'event_state': 'Rhode Island',
            'event_country': 'United States',
            'event_location': 'Providence, RI, United States',
            'event_location_standardized': 'Providence, RI',
        },
    },
    384: {
        'name': 'Grand Party Sofia (GPS)',
        'url': 'https://wcs-gps.com/',
        'typical_location': 'Sofia, Bulgaria',
        'location': {
            'event_city': 'Sofia',
            'event_state': '',
            'event_country': 'Bulgaria',
            'event_location': 'Sofia, Bulgaria',
            'event_location_standardized': 'Sofia, Bulgaria',
        },
    },
    369: {
        'name': 'FRENCH CONNECTION WCS',
        'url': 'http://FRENCHCONNECTIONWCS.COM',
        'typical_location': 'Annecy, France',
        'location': {
            'event_city': 'Annecy',
            'event_state': '',
            'event_country': 'France',
            'event_location': 'Annecy, France',
            'event_location_standardized': 'Annecy, France',
        },
    },
    324: {
        'name': 'BTO Open',
        'url': 'https://ctodance.ca/',
        'typical_location': 'Calgary, Alberta, Canada',
    },
    380: {
        'name': 'SASS Spooky Albany Swing Spectacular',
        'url': 'http://www.spookyalbanyswing.com/',
        'typical_location': 'Albany, NY, United States',
    },
    323: {
        'url': 'http://rocketcityswing.com/',
        'typical_location': 'Huntsville, Alabama, United States',
    },
}

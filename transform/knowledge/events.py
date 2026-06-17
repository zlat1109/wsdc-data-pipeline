"""Event name/location correction maps and catalog metadata."""

from __future__ import annotations

from typing import Any

EVENT_NAME_NORMALIZATION = {
    'Scandinavian Open WCS': 'Scandinavian Open',
    'Scandinavian Open WCS 2022': 'Scandinavian Open',
    'Scandinavian Open WCS "SNOW"': 'Scandinavian Open',
    'Americano Dance camp': 'Americano Dance Camp',
    'Rock The Barn': 'Rock the Barn',
    'Go West Swingfest': 'Go West SwingFest',
    'D-TOWNSWING': 'D-Townswing',
    'KING SWING': 'King Swing',
    'SWINGAPALOOZA': 'Swingapalooza',
    'London SWINGvitational': 'London SwingVitational',
    'Westies on The Water': 'Westies on the Water',
    'Boogie by the Bay': 'Boogie By The Bay',
    'Swingvester': 'SwingVester',
    'West In Lyon': 'West in Lyon',
    'Paradise dance festival': 'Paradise Dance Festival',
    'WESTY NANTES': 'Westy Nantes',
    'BALTIC SWING': 'Baltic Swing',
    'Halloween Swingthing': 'Halloween SwingThing',
    'By-Town Open (BTO)': 'BTO Open',
}

EVENT_NAME_LOCATION_OVERRIDES = {
    'Go West Swing Fest': 'Fremantle, Australia',
    'BeeMAD': 'Madrid, Spain',
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
    'Concord CA': 'Concord, CA',
    'St. Burlatskaya, Russia': 'Samara, Russia',
    'CHICAGO, IL, United States': 'Chicago, IL, United States',
    'St. Louis, Mo, USA': 'St. Louis, MO, USA',
    'PARIS, France': 'Paris, France',
    'Moscow,  Russia': 'Moscow, Russia',
    'Stockholm,  Sweden': 'Stockholm, Sweden',
    'Singapore': 'Singapore, Singapore',
    'New York': 'New York, NY',
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

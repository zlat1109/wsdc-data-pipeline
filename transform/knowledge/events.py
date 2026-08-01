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
    # Same Perth-area brand, separate WSDC event_id 367 (2024+); keep distinct from 306.
    'Go West SwingFest': 'Perth, Australia',
    'BeeMAD': 'Madrid, Spain',
    # Shared Wailea (124 / Aloha Open) wrongly applied to Swedish events.
    'Sweden Westie Gala': 'Stockholm, Sweden',
    'Westie Gala': 'Stockholm, Sweden',
    'Swedish Swing Summer Camp': 'Stockholm, Sweden',
    'UpTown Swing': 'Stockholm, Sweden',
    # Shared Washington DC (13) wrongly applied to Valentine Swing (Johannesberg Castle, SE).
    'Valentine Swing': 'Stockholm, Sweden',
    # Shared Washington DC (13) metro label — venues are Hyatt Regency Dulles, Herndon VA.
    'Swing Fling': 'Herndon, VA, United States',
    'DC Swing eXperience (DCSX)': 'Herndon, VA, United States',
    # Shared St. Petersburg (222) wrongly applied to Toronto Open.
    'Toronto Open Swing & Hustle Championships': 'Toronto, Canada',
    # Shared St. Petersburg (222) wrongly applied to Revitalise WCS (Melbourne).
    'Revitalise WCS': 'Melbourne, Australia',
    # Calendar/site Montreal; results stuck on shared New York (7).
    'Montreal Westie Fest': 'Montreal, Canada',
    # Catalog upcoming + 2026 schedule Jeju; results stuck on shared Brno (266).
    # Flat override (not year-aware): historical Korean cities may differ, but Brno is wrong.
    'Korea Westival': 'Jeju, Republic of Korea',
    # Calendar/site Warsaw; results stuck on shared Washington DC (13).
    'Warsaw Summer Nights Westival': 'Warsaw, Poland',
    # Calendar/site Östersund; results stuck on shared Phoenix (3).
    'Mooseland Swing': 'Östersund, Sweden',
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
    # Shared Brno (266 / Swing Fiction) wrongly applied to Berlin events.
    'SwingLab Berlin': 'Berlin, Germany',
    'Berlin Swing Revolution': 'Berlin, Germany',
    # Shared Wailea (124 / Aloha Open lineage) wrongly applied to SaunaSwing (Finland).
    'SaunaSwing': 'Ikaalinen, Finland',
    # Shared Venray (227 / Dutch Open) wrongly applied to Freedom Swing (Wilmington DE).
    # Catalog upcoming already says WILMINGTON DEL; typical was stuck on Venray.
    'Freedom Swing Dance Challenge': 'Wilmington, DE, United States',
    # Philly Swing Classic is held in Wilmington, Delaware.
    'Philly Swing Classic': 'Wilmington, DE, United States',
    # Shared St. Petersburg (222) wrongly applied to West in Lyon (name + calendar = Lyon).
    'West in Lyon': 'Lyon, France',
    # Registry/site venue is Rome; legacy results were mapped to St. Petersburg (222).
    'Swing In Capital': 'Rome, Italy',
    # Registry/site venue is Ljubljana; legacy results were mapped to Perth (253).
    'Slovenian Open': 'Ljubljana, Slovenia',
    # Official site: Freiburg, Germany; legacy rows were mapped to Jeju (213).
    'Spring Time Swing': 'Freiburg, Germany',
    # Official site seasunswing.fr / calendar: La Grande Motte; all results stuck on Jeju (213).
    'Sea Sun and Swing': 'La Grande Motte, France',
    # Catalog/scheduled say Calgary; results pointed at Perth (253 / WesterOz).
    'BTO Open': 'Calgary, Canada',
    # Shared Jeju (213) wrongly applied to The Aloha Open (Wailea / Hawaii).
    'The Aloha Open': 'Wailea, HI, United States',
    # Shared Düsseldorf (127) wrongly applied to Sea Dance Fest (Moscow).
    'Sea Dance Fest': 'Moscow, Russia',
    # Shared Phoenix (3 / Desert City etc.) wrongly applied to Med in Swing (Côte d'Azur).
    'Med in Swing': 'La Londe-les-Maures, France',
    # Shared Washington DC (13) wrongly applied to Westie's Angels (Lyon).
    "Westie's Angels": 'Lyon, France',
    # Shared San Antonio (167) wrongly applied to Swingside Invitational (Liège).
    'Swingside Invitational': 'Liège, Belgium',
    # Fresh main export: more shared-wrong location_id collisions (calendar ≠ results).
    'Bavarian Open': 'Munich, Germany',  # was Jeju (213)
    'King Swing': 'Kraków, Poland',  # was Wailea (124)
    'Santa Swing': 'Kraków, Poland',  # was Wailea (124)
    'Westy Nantes': 'Nantes, France',  # was Brno (266)
    'Paris Westie Fest': 'Paris, France',  # was Venray (227)
    'Rolling Swing': 'Lyon, France',  # was Phoenix (3)
    'Dutch Open West Coast Swing': 'Venray, Netherlands',  # was Perth (253)
    # Shared Venray (227 / Dutch Open) wrongly applied to Best of the Best (Sydney, AU).
    'Best of the Best WCS': 'Sydney, Australia',
    'Winter Coast Swing': 'Kuopio, Finland',  # was Düsseldorf (127)
    # Shared St. Petersburg (222 / Swing & Snow) wrongly applied to NZ Open.
    # Site/URL streetswing.co.nz; calendar sibling in Auckland.
    'New Zealand Open Swing Dance Championships': 'Auckland, New Zealand',
    # WSDC venue label "Boston Club" is in Düsseldorf (not a city name).
    'D-Town Swing': 'Düsseldorf, Germany',
    'WCS Festival': 'Düsseldorf, Germany',
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
    'WILMINGTON DEL, Delaware, United States': 'Wilmington, DE, United States',
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
    271: {
        'name': 'Berlin Swing Revolution',
        'url': '',
        'typical_location': 'Berlin, Germany',
        'location': {
            'event_city': 'Berlin',
            'event_state': '',
            'event_country': 'Germany',
            'event_location': 'Berlin, Germany',
            'event_location_standardized': 'Berlin, Germany',
        },
    },
    360: {
        'name': 'SaunaSwing',
        'url': 'https://ekarolas.com/saunaswing/',
        'typical_location': 'Ikaalinen, Finland',
        'location': {
            'event_city': 'Ikaalinen',
            'event_state': '',
            'event_country': 'Finland',
            'event_location': 'Ikaalinen, Finland',
            'event_location_standardized': 'Ikaalinen, Finland',
        },
    },
    183: {
        'name': 'Freedom Swing Dance Challenge',
        'url': 'https://freedomswingdance.com/',
        'typical_location': 'Wilmington, DE, United States',
        'location': {
            'event_city': 'Wilmington',
            'event_state': 'Delaware',
            'event_country': 'United States',
            'event_location': 'Wilmington, DE, United States',
            'event_location_standardized': 'Wilmington, DE',
        },
    },
    234: {
        'name': 'Philly Swing Classic',
        'url': 'http://www.phillyswing.com',
        'typical_location': 'Wilmington, DE, United States',
        'location': {
            'event_city': 'Wilmington',
            'event_state': 'Delaware',
            'event_country': 'United States',
            'event_location': 'Wilmington, DE, United States',
            'event_location_standardized': 'Wilmington, DE',
        },
    },
    186: {
        'name': 'West in Lyon',
        'url': '',
        'typical_location': 'Lyon, France',
        'location': {
            'event_city': 'Lyon',
            'event_state': '',
            'event_country': 'France',
            'event_location': 'Lyon, France',
            'event_location_standardized': 'Lyon, France',
        },
    },
    355: {
        'name': 'The Aloha Open',
        'url': '',
        'typical_location': 'Wailea, HI, United States',
        'location': {
            'event_city': 'Wailea',
            'event_state': 'Hawaii',
            'event_country': 'United States',
            'event_location': 'Wailea, HI, United States',
            'event_location_standardized': 'Wailea, HI',
        },
    },
    338: {
        'name': 'Sea Dance Fest',
        'url': 'https://vk.com/seadancefest',
        'typical_location': 'Moscow, Russia',
        'location': {
            'event_city': 'Moscow',
            'event_state': '',
            'event_country': 'Russia',
            'event_location': 'Moscow, Russia',
            'event_location_standardized': 'Moscow, Russia',
        },
    },
    270: {
        'name': "Westie's Angels",
        'url': '',
        'typical_location': 'Lyon, France',
        'location': {
            'event_city': 'Lyon',
            'event_state': '',
            'event_country': 'France',
            'event_location': 'Lyon, France',
            'event_location_standardized': 'Lyon, France',
        },
    },
    346: {
        'name': 'Swingside Invitational',
        'url': '',
        'typical_location': 'Liège, Belgium',
        'location': {
            'event_city': 'Liège',
            'event_state': '',
            'event_country': 'Belgium',
            'event_location': 'Liège, Belgium',
            'event_location_standardized': 'Liège, Belgium',
        },
    },
    379: {
        'name': 'Med in Swing',
        'url': 'http://www.medinswing.rocks',
        'typical_location': 'La Londe-les-Maures, France',
        'location': {
            'event_city': 'La Londe-les-Maures',
            'event_state': '',
            'event_country': 'France',
            'event_location': 'La Londe-les-Maures, France',
            'event_location_standardized': 'La Londe-les-Maures, France',
        },
    },
    389: {
        'name': 'SwingLab Berlin',
        'url': 'http://www.swinglab-berlin.com',
        'typical_location': 'Berlin, Germany',
        'location': {
            'event_city': 'Berlin',
            'event_state': '',
            'event_country': 'Germany',
            'event_location': 'Berlin, Germany',
            'event_location_standardized': 'Berlin, Germany',
        },
    },
    405: {
        'name': 'Milan Swing Vibes',
        'url': '',
        'typical_location': 'Milan, Italy',
        'location': {
            'event_city': 'Milan',
            'event_state': '',
            'event_country': 'Italy',
            'event_location': 'Milan, Italy',
            'event_location_standardized': 'Milan, Italy',
        },
    },
    233: {
        'name': 'Bavarian Open',
        'url': 'https://bavarianopen.com/',
        'typical_location': 'Munich, Germany',
        'location': {
            'event_city': 'Munich',
            'event_state': '',
            'event_country': 'Germany',
            'event_location': 'Munich, Germany',
            'event_location_standardized': 'Munich, Germany',
        },
    },
    292: {
        'name': 'King Swing',
        'url': 'https://kingswing.pl/',
        'typical_location': 'Kraków, Poland',
        'location': {
            'event_city': 'Kraków',
            'event_state': '',
            'event_country': 'Poland',
            'event_location': 'Kraków, Poland',
            'event_location_standardized': 'Kraków, Poland',
        },
    },
    377: {
        'name': 'Santa Swing',
        'url': 'https://www.santaswing.pl/',
        'typical_location': 'Kraków, Poland',
        'location': {
            'event_city': 'Kraków',
            'event_state': '',
            'event_country': 'Poland',
            'event_location': 'Kraków, Poland',
            'event_location_standardized': 'Kraków, Poland',
        },
    },
    293: {
        'name': 'Westy Nantes',
        'url': 'https://www.westynantes.com/',
        'typical_location': 'Nantes, France',
        'location': {
            'event_city': 'Nantes',
            'event_state': '',
            'event_country': 'France',
            'event_location': 'Nantes, France',
            'event_location_standardized': 'Nantes, France',
        },
    },
    272: {
        'name': 'Paris Westie Fest',
        'url': '',
        'typical_location': 'Paris, France',
        'location': {
            'event_city': 'Paris',
            'event_state': '',
            'event_country': 'France',
            'event_location': 'Paris, France',
            'event_location_standardized': 'Paris, France',
        },
    },
    313: {
        'name': 'Rolling Swing',
        'url': 'http://www.frenchywesty.com/',
        'typical_location': 'Lyon, France',
        'location': {
            'event_city': 'Lyon',
            'event_state': '',
            'event_country': 'France',
            'event_location': 'Lyon, France',
            'event_location_standardized': 'Lyon, France',
        },
    },
    275: {
        'name': 'Dutch Open West Coast Swing',
        'url': 'http://www.dutchopenwcs.com/',
        'typical_location': 'Venray, Netherlands',
        'location': {
            'event_city': 'Venray',
            'event_state': '',
            'event_country': 'Netherlands',
            'event_location': 'Venray, Netherlands',
            'event_location_standardized': 'Venray, Netherlands',
        },
    },
    297: {
        'name': 'Winter Coast Swing',
        'url': 'https://www.wintercoastswing.com/',
        'typical_location': 'Kuopio, Finland',
        'location': {
            'event_city': 'Kuopio',
            'event_state': '',
            'event_country': 'Finland',
            'event_location': 'Kuopio, Finland',
            'event_location_standardized': 'Kuopio, Finland',
        },
    },
    179: {
        'name': 'New Zealand Open Swing Dance Championships',
        'url': 'https://www.streetswing.co.nz/the-new-zealand-open',
        'typical_location': 'Auckland, New Zealand',
        'location': {
            'event_city': 'Auckland',
            'event_state': '',
            'event_country': 'New Zealand',
            'event_location': 'Auckland, New Zealand',
            'event_location_standardized': 'Auckland, New Zealand',
        },
    },
    220: {
        'name': 'D-Town Swing',
        'url': 'http://www.d-townswing.com/',
        'typical_location': 'Düsseldorf, Germany',
        'location': {
            'event_city': 'Düsseldorf',
            'event_state': '',
            'event_country': 'Germany',
            'event_location': 'Düsseldorf, Germany',
            'event_location_standardized': 'Düsseldorf, Germany',
        },
    },
    286: {
        'name': 'WCS Festival',
        'url': 'http://www.wcsfestival.com/',
        'typical_location': 'Düsseldorf, Germany',
        'location': {
            'event_city': 'Düsseldorf',
            'event_state': '',
            'event_country': 'Germany',
            'event_location': 'Düsseldorf, Germany',
            'event_location_standardized': 'Düsseldorf, Germany',
        },
    },

    240: {
        'name': 'Westie Gala',
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
    493: {
        'name': 'UpTown Swing',
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
    310: {
        'name': 'Valentine Swing',
        'url': 'http://www.valentineswing.dance',
        'typical_location': 'Stockholm, Sweden',
        'location': {
            'event_city': 'Stockholm',
            'event_state': '',
            'event_country': 'Sweden',
            'event_location': 'Stockholm, Sweden',
            'event_location_standardized': 'Stockholm, Sweden',
        },
    },
    59: {
        'name': 'Swing Fling',
        'url': 'http://www.swingfling.com',
        'typical_location': 'Herndon, VA, United States',
        'location': {
            'event_city': 'Herndon',
            'event_state': 'Virginia',
            'event_country': 'United States',
            'event_location': 'Herndon, VA, United States',
            'event_location_standardized': 'Herndon, VA, United States',
        },
    },
    181: {
        'name': 'DC Swing eXperience (DCSX)',
        'url': 'http://www.dcswingexperience.com',
        'typical_location': 'Herndon, VA, United States',
        'location': {
            'event_city': 'Herndon',
            'event_state': 'Virginia',
            'event_country': 'United States',
            'event_location': 'Herndon, VA, United States',
            'event_location_standardized': 'Herndon, VA, United States',
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
        'typical_location': 'Calgary, Canada',
        'location': {
            'event_city': 'Calgary',
            'event_state': '',
            'event_country': 'Canada',
            'event_location': 'Calgary, Canada',
            'event_location_standardized': 'Calgary, Canada',
        },
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
    18: {
        'name': 'Easter Swing',
        'url': 'https://easterswing.org/',
        'typical_location': 'Seattle, WA, United States',
        'location': {
            'event_city': 'Seattle',
            'event_state': 'Washington',
            'event_country': 'United States',
            'event_location': 'Seattle, WA, United States',
            'event_location_standardized': 'Seattle, WA',
        },
    },
    92: {
        'name': 'MADjam',
        'url': 'http://www.atlanticdancejam.com',
        'typical_location': 'Washington, DC, United States',
        'location': {
            'event_city': 'Washington',
            'event_state': 'District of Columbia',
            'event_country': 'United States',
            'event_location': 'Washington, DC, United States',
            'event_location_standardized': 'Washington, DC',
        },
    },
    354: {
        'name': 'Spring Time Swing',
        'url': 'https://springtimeswing.com/',
        'typical_location': 'Freiburg, Germany',
        'location': {
            'event_city': 'Freiburg',
            'event_state': '',
            'event_country': 'Germany',
            'event_location': 'Freiburg, Germany',
            'event_location_standardized': 'Freiburg, Germany',
        },
    },
    304: {
        'name': 'Swing In Capital',
        'url': 'https://www.westcoastswingroma.it/swing-in-capital/',
        'typical_location': 'Rome, Italy',
        'location': {
            'event_city': 'Rome',
            'event_state': '',
            'event_country': 'Italy',
            'event_location': 'Rome, Italy',
            'event_location_standardized': 'Rome, Italy',
        },
    },
    352: {
        'name': 'Slovenian Open',
        'url': 'https://slovenianopen.dance/',
        'typical_location': 'Ljubljana, Slovenia',
        'location': {
            'event_city': 'Ljubljana',
            'event_state': '',
            'event_country': 'Slovenia',
            'event_location': 'Ljubljana, Slovenia',
            'event_location_standardized': 'Ljubljana, Slovenia',
        },
    },
    167: {
        'name': 'Best of the Best WCS',
        'url': 'https://www.bestofthebestwcs.com/',
        'typical_location': 'Sydney, Australia',
        'location': {
            'event_city': 'Sydney',
            'event_state': '',
            'event_country': 'Australia',
            'event_location': 'Sydney, Australia',
            'event_location_standardized': 'Sydney, Australia',
        },
    },
    164: {
        'name': 'Sea Sun and Swing',
        'url': 'https://www.seasunswing.fr/',
        'typical_location': 'La Grande Motte, France',
        'location': {
            'event_city': 'La Grande Motte',
            'event_state': '',
            'event_country': 'France',
            'event_location': 'La Grande Motte, France',
            'event_location_standardized': 'La Grande Motte, France',
        },
    },
}

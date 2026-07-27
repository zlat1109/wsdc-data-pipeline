"""Location correction maps for location_info."""

from __future__ import annotations

LocationPatch = dict[str, str]

# WSDC city-states where event_city = event_country is valid (not a geocode bug).
CITY_STATE_COUNTRIES: frozenset[str] = frozenset({"Singapore"})

# Canonical Singapore row in location_info (has coordinates).
SINGAPORE_CANONICAL_LOCATION_ID = 159
SAN_ANTONIO_CANONICAL_LOCATION_ID = 167

# WSDC malformed location strings → canonical text (preprocess + resolve lookup).
LOCATION_RAW_ALIASES: dict[str, str] = {
    "San antonio, Texas, United states": "San Antonio, TX, United States",
    "Phoenix, United States": "Phoenix, AZ, United States",
    "Washington, United States": "Washington, DC, United States",
    # WSDC metro label for Dance Jam / Westie Weekend @ Hollywood Ballroom
    "Washington, MD, United States": "Silver Spring, MD, United States",
    "Wailea, United States": "Wailea, HI, United States",
    "Gdansk, Poland": "Gdańsk, Poland",
    # Venue name used by WSDC for Düsseldorf (D-Town Swing / WCS Festival)
    "Boston Club, Germany": "Düsseldorf, Germany",
    "Boston Club, NRW, Germany": "Düsseldorf, Germany",
    # Airport / suburb label for Global Grand Prix → city Toulouse
    "Toulouse-Blagnac, France": "Toulouse, France",
}

# Duplicate location_id rows → canonical location_id (remap FKs, delete source row).
LOCATION_ID_MERGE_MAP: dict[str, str] = {
    "244": str(SINGAPORE_CANONICAL_LOCATION_ID),
    "350": str(SINGAPORE_CANONICAL_LOCATION_ID),
    # Albany duplicate — 139 carries every result and edition
    "161": "139",
    # Amsterdam — keep 191 (coordinates)
    "373": "191",
    # Anaheim / Garden Grove metro → Anaheim
    "291": "23",
    "470": "23",
    # Boston Club venue label → Düsseldorf
    "334": "127",
    "436": "127",
    "365": "127",  # current export id for Boston Club, Germany (D-Town / WCS Festival)
    # Brno country alias
    "412": "266",
    # Calgary duplicate
    "345": "148",
    # Dallas Ft. Worth → Dallas
    "295": "21",
    # Duesseldorf spelling → Düsseldorf
    "198": "127",
    # Edmonton duplicate
    "380": "205",
    # Incheon / Jeju country alias (South Korea → Republic of Korea canonical)
    "359": "172",
    "382": "213",
    "467": "213",
    "395": "213",
    # Ft. Lauderdale spelling → Fort Lauderdale
    "302": "55",
    # Montreal duplicate
    "331": "86",
    # N. Myrtle Beach abbreviation → North Myrtle Beach (canonical id 325)
    "111": "325",
    # New York City → New York
    "224": "7",
    "388": "7",
    # Perth state-as-country typo
    "423": "253",
    # Phoenix country typo
    "287": "3",
    "426": "3",
    # Richmond duplicate
    "335": "128",
    # San Antonio casing / country typo
    "355": "167",
    "445": str(SAN_ANTONIO_CANONICAL_LOCATION_ID),
    # St.Petersburg spelling
    "401": "222",
    # Tampa Bay → Tampa
    "300": "53",
    # Toronto duplicate
    "363": "105",
    # Stockholm duplicate — 199 is canonical and already carries coordinates
    "231": "199",
    # Toulouse-Blagnac airport label → Toulouse (keep 208 with coordinates)
    "187": "208",
    "369": "208",
    "385": "208",  # current export: Toulouse-Blagnac without lat/lon (Null Island in Tableau)
    # Vancouver duplicate
    "347": "154",
    # Venray duplicate (keep row with coordinates)
    "391": "227",
    # Wailea duplicate
    "333": "124",
    "435": "124",
    # Ambiguous "Washington" (MD suburb / non-DC events in audit) → Washington DC id 13
    "310": "13",
    # DCSX — country-only label
    "428": "13",
}

# Extra lookup keys → canonical location_id (lowercase event_location text).
# Add entries when reconciliation finds a new WSDC string that maps to a known id.
LOCATION_STRING_ALIASES: dict[str, str] = {
    "singapore": str(SINGAPORE_CANONICAL_LOCATION_ID),
    "singapore, singapore": str(SINGAPORE_CANONICAL_LOCATION_ID),
    "singapore, singapore, singapore": str(SINGAPORE_CANONICAL_LOCATION_ID),
    "amsterdam, netherlands": "191",
    "anaheim, ca, united states": "23",
    "anaheim/garden grove, ca, united states": "23",
    "garden grove, ca, united states": "23",
    "ft. lauderdale, fl, united states": "55",
    "fort lauderdale, fl, united states": "55",
    "boston club, germany": "127",
    "dusseldorf, germany": "127",
    "duesseldorf, germany": "127",
    "brno, czech republic": "266",
    "brno, czechia": "266",
    "toulouse-blagnac, france": "208",
    "new york city, ny, united states": "7",
    "tampa bay, fl, united states": "53",
    "dallas ft. worth, tx, united states": "21",
    "dallas ft worth, tx, united states": "21",
    "st.petersburg, russia": "222",
    "st petersburg, russia": "222",
    "incheon, south korea": "172",
    "jeju, south korea": "213",
    "perth, western australia, australia": "253",
    "phoenix, usa": "3",
    "phoenix, united states": "3",
    "san antonio, texas, united states": str(SAN_ANTONIO_CANONICAL_LOCATION_ID),
    "san antonio, tx, united states": str(SAN_ANTONIO_CANONICAL_LOCATION_ID),
    "washington, united states": "13",
    "washington, md, united states": "353",
    "silver spring, md, united states": "353",
    "wailea, united states": "124",
    "london, england, united kingdom": "107",
    "north myrtle beach, sc, united states": "325",
    "n. myrtle beach, sc, united states": "325",
}

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
    213: {
        'event_city': 'Jeju',
        'event_state': '',
        'event_country': 'Republic of Korea',
        'event_location': 'Jeju, Republic of Korea',
        'event_location_standardized': 'Jeju, Republic of Korea',
    },
    139: {
        'event_city': 'Albany',
        'event_state': 'New York',
        'event_country': 'United States',
        'event_location': 'Albany, NY, United States',
        'event_location_standardized': 'Albany, NY',
    },
    # Non-US: event_state only for United States
    191: {
        'event_city': 'Amsterdam',
        'event_state': '',
        'event_country': 'Netherlands',
        'event_location': 'Amsterdam, Netherlands',
        'event_location_standardized': 'Amsterdam, Netherlands',
    },
    227: {
        'event_city': 'Venray',
        'event_state': '',
        'event_country': 'Netherlands',
        'event_location': 'Venray, Netherlands',
        'event_location_standardized': 'Venray, Netherlands',
    },
    107: {
        'event_city': 'London',
        'event_state': '',
        'event_country': 'United Kingdom',
        'event_location': 'London, United Kingdom',
        'event_location_standardized': 'London, United Kingdom',
    },
    234: {
        'event_city': 'Bristol',
        'event_state': '',
        'event_country': 'United Kingdom',
        'event_location': 'Bristol, United Kingdom',
        'event_location_standardized': 'Bristol, United Kingdom',
    },
    226: {
        'event_city': 'Glasgow',
        'event_state': '',
        'event_country': 'United Kingdom',
        'event_location': 'Glasgow, United Kingdom',
        'event_location_standardized': 'Glasgow, United Kingdom',
    },
    86: {
        'event_city': 'Montreal',
        'event_state': '',
        'event_country': 'Canada',
        'event_location': 'Montreal, Canada',
        'event_location_standardized': 'Montreal, Canada',
    },
    105: {
        'event_city': 'Toronto',
        'event_state': '',
        'event_country': 'Canada',
        'event_location': 'Toronto, Canada',
        'event_location_standardized': 'Toronto, Canada',
    },
    128: {
        'event_city': 'Richmond',
        'event_state': '',
        'event_country': 'Canada',
        'event_location': 'Richmond, Canada',
        'event_location_standardized': 'Richmond, Canada',
    },
    148: {
        'event_city': 'Calgary',
        'event_state': '',
        'event_country': 'Canada',
        'event_location': 'Calgary, Canada',
        'event_location_standardized': 'Calgary, Canada',
    },
    154: {
        'event_city': 'Vancouver',
        'event_state': '',
        'event_country': 'Canada',
        'event_location': 'Vancouver, Canada',
        'event_location_standardized': 'Vancouver, Canada',
    },
    179: {
        'event_city': 'Ottawa',
        'event_state': '',
        'event_country': 'Canada',
        'event_location': 'Ottawa, Canada',
        'event_location_standardized': 'Ottawa, Canada',
    },
    205: {
        'event_city': 'Edmonton',
        'event_state': '',
        'event_country': 'Canada',
        'event_location': 'Edmonton, Canada',
        'event_location_standardized': 'Edmonton, Canada',
    },
    127: {
        'event_city': 'Düsseldorf',
        'event_state': '',
        'event_country': 'Germany',
        'event_location': 'Düsseldorf, Germany',
        'event_location_standardized': 'Düsseldorf, Germany',
    },
    325: {
        'event_city': 'North Myrtle Beach',
        'event_state': 'South Carolina',
        'event_country': 'United States',
        'event_location': 'North Myrtle Beach, SC, United States',
        'event_location_standardized': 'North Myrtle Beach, SC',
        'latitude': '33.8160058',
        'longitude': '-78.680016',
    },
    353: {
        # Dance Jam Jack & Jill Weekend / Westie Weekend — Hollywood Ballroom
        'event_city': 'Silver Spring',
        'event_state': 'Maryland',
        'event_country': 'United States',
        'event_location': 'Silver Spring, MD, United States',
        'event_location_standardized': 'Silver Spring, MD',
        'latitude': '38.9906654',
        'longitude': '-77.026088',
        'coordinates_valid': 't',
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

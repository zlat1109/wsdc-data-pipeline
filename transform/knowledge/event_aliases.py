"""Result-side event names → WSDC catalog names (core.events.name).

Points export often uses marketing / shortened titles; core.events keeps registry
names from events_wsdc. Preprocess maps aliases to catalog; load seeds
core.event_aliases as a second line of defense.
"""

from __future__ import annotations

# Result / marketing name → exact core.events.name (must match events_wsdc.csv).
RESULT_TO_CATALOG_EVENT_NAME: dict[str, str] = {
    'Phoenix 4th of July': '4TH of July Convention',
    'Easter Swing': "Seattle's Easter Swing",
    'MADjam': 'Mid-Atlantic Dance Jam',
    'Monterey Swing Fest': 'Monterey SwingFest',
    'SwingTime': 'Swingtime in the Rockies',
    "Swingin' New England": "Swingin' New England Dance Festival",
    'Palm Springs New Year': 'Palm Springs New Years Swing Dance Classic',
    'Palm Springs Swing Dance Classic': 'Palm Springs Summer Dance Classic',
    'French Open WCS': 'French Open West Coast Swing',
    'DC Swing eXperience': 'DC Swing eXperience (DCSX)',
    'BridgeTown Swing': 'Bridgetown Swing Boogie',
    'City of Angels': 'City of Angels WCS',
    'Spotlight Dance Challenge': "Spotlight New Year's Celebration",
    'Michigan Classic': 'Michigan Dance Classic',
    'The After Party': 'The After Party (TAP)',
    'C.A.S.H. Bash Weekend': 'CASH Bash',
    'Swingtacular': 'Swingtacular: The Galactic Open',
    'Chicagoland Dance Festival': 'Chicagoland Country and Swing Dance Festival',
    'D-Townswing': 'D-Town Swing',
    'Swing Over': 'Swingover',
    'Asia WCS Open': 'Asia West Coast Swing Open',
    'Toronto Open': 'Toronto Open Swing & Hustle Championships',
    'Westie Gala': 'Sweden Westie Gala',
    'Best of the Best': 'Best of the Best WCS',
    'St.Petersburg WCS Nights': 'Saint Petersburg WCS Nights',
    'Russian Open': 'Russian Open WCS Championships',
    'UpTown Swing': 'Swedish Swing Summer Camp',
    'New Zealand Open': 'New Zealand Open Swing Dance Championships',
    'Dutch Open': 'Dutch Open West Coast Swing',
    'Global Grand Prix': 'Global Grand Prix - West Coast Swing Reunion',
    'The Open World Swing Dance Championships': 'World Swing Dance Championships',
    'Korean Open': 'Korean Open WCS Championships',
    'UK West Coast Swing Championships': 'UK WCS Championships',
    'Jax Westie Fest': 'River City Swing',
    'Rocket City Swing': 'Westies on the Water',
    'H-Town Throw Down': 'Novice Invitational',
    'SOM-Swing of Music': 'SOM - Swing of Music',
    'Swing of Music': 'SOM - Swing of Music',
    'Westie Weekend': 'Dance Jam Jack & Jill Weekend',
}

# Spelling / casing variants → catalog name (not intermediate result labels).
EVENT_NAME_VARIANT_TO_CATALOG: dict[str, str] = {
    'Scandinavian Open WCS': 'Scandinavian Open',
    'Scandinavian Open WCS 2022': 'Scandinavian Open',
    'Scandinavian Open WCS "SNOW"': 'Scandinavian Open',
    'Americano Dance camp': 'Americano Dance Camp',
    'Rock The Barn': 'Rock the Barn',
    'Go West Swingfest': 'Go West SwingFest',
    'D-TOWNSWING': 'D-Town Swing',
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


def build_event_name_normalization() -> dict[str, str]:
    """Single preprocess map: every key resolves to a core.events.name."""
    merged: dict[str, str] = {}
    merged.update(EVENT_NAME_VARIANT_TO_CATALOG)
    merged.update(RESULT_TO_CATALOG_EVENT_NAME)
    return merged

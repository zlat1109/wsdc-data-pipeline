"""Result-side event names → WSDC catalog names (core.events.name).

Points export often uses marketing / shortened titles; core.events keeps registry
names from events_wsdc. Preprocess maps aliases to catalog; load seeds
core.event_aliases as a second line of defense.
"""

from __future__ import annotations

import pandas as pd

from transform.pandas_utils import assign_column_values

# Result / marketing name → exact core.events.name (must match events_wsdc.csv).
RESULT_TO_CATALOG_EVENT_NAME: dict[str, str] = {
    'Phoenix 4th of July': '4TH of July Convention',
    "Seattle's Easter Swing": 'Easter Swing',
    'Easter Swing': 'Easter Swing',
    'MADjam': 'MADjam',
    'Mid-Atlantic Dance Jam': 'MADjam',
    'MADjam (Mid Atlantic Dance Jam)': 'MADjam',
    'Mid Atlantic Dance Jam (MADjam)': 'MADjam',
    'Midnight Madness Swing': 'Midnight Madness',
    'Midnight Madness WCS': 'Midnight Madness',
    'Swing Open Kazan': 'Kazan EL Fest',
    'UK & European WCS Championships': 'UK WCS Championships',
    'UK WCS Dance Championships': 'UK WCS Championships',
    'USA Grand National Dance Championships': 'USA Grand Nationals',
    'USA Grand Nationals Dance Championship': 'USA Grand Nationals',
    'USA Grand Nationals Dance Championships': 'USA Grand Nationals',
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
    'Sweden Westie Gala': 'Westie Gala',
    'Vestigala': 'Westie Gala',
    'Westigala': 'Westie Gala',
    'Best of the Best': 'Best of the Best WCS',
    'St.Petersburg WCS Nights': 'Saint Petersburg WCS Nights',
    'Russian Open': 'Russian Open WCS Championships',
    # UpTown Swing is the post-2018 name; year split applied separately.
    # Do NOT map UpTown → Swedish Swing Summer Camp (that collapses the series).
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
    # Real series title in results/events_wsdc; ghost catalog used old Championships name.
    '5280 Swing Dance Championships': '5280 Westival',
    'LoneStar Invitational': 'Lone Star Invitational',
    'Lonestar Invitational': 'Lone Star Invitational',
    'French Connection WCS': 'FRENCH CONNECTION WCS',
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
    'Monterey Swingfest': 'Monterey SwingFest',
    'Monterey Swing Fest 2024': 'Monterey SwingFest',
    'Swing Fling 2024': 'Swing Fling',
    'Easter Swing 2026': 'Easter Swing',
    'Austin Rocks 2024': 'Austin Rocks',
    'Midwest Westie Fest 2025': 'Midwest Westie Fest',
    'Milan Modern Swing 2025': 'Milan Modern Swing',
    'Mooseland Swing 2025': 'Mooseland Swing',
    'SOswing 2022': 'SOswing',
    'Korea Westival 2025': 'Korea Westival',
    'Dutch Open West Coast Swing 2024': 'Dutch Open West Coast Swing',
    'Simply Adelaide West Coast Swing 2022': 'Simply Adelaide West Coast Swing',
    'Simply Adelaide West Coast Swing 2023': 'Simply Adelaide West Coast Swing',
    'Simply Adelaide West Coast Swing 2024': 'Simply Adelaide West Coast Swing',
    'Swing Fiction 2024': 'Swing Fiction',
    'Floorplay New Years Swing Vacation': 'FloorPlay New Years Swing Vacation',
    'DC Swing Experience (DCSX)': 'DC Swing eXperience (DCSX)',
    'UK WCS Championships': 'UK WCS Championships',
    'U.K. & European WCS Championships': 'UK WCS Championships',
    'UK & European WCS Championships': 'UK WCS Championships',
    'UK WCS Dance Championships': 'UK WCS Championships',
    'Swing&Snow': 'Swing & Snow',
    'Moscow Westie Fest Gala Edition': 'Moscow Westie Fest',
    'Moscow Westie Dance Fest': 'Moscow Westie Fest',
    'NeverlandSwing Dutch Swing Championships 2026': 'Neverland Swing',
    'NeverlandSwing Dutch Swing Championships': 'Neverland Swing',
    'Paris Swing Classic': 'Paris Westie Fest',
    'The Boston Tea Party': 'Boston Tea Party',
    'Capital Swing Convention': 'Capital Swing Dance Convention',
    'The New Zealand West Coast Swing Open': 'New Zealand Open Swing Dance Championships',
    'BaroqueSwing': 'Barock Swing Ludwigsburg',
}

# Duplicate WSDC registry ids → canonical id (same geo; see event-geo-dedup rule).
# Source id rows are remapped in core.results; sources are not deleted.
MERGE_EVENT_ID_MAP: dict[int, int] = {
    66: 47,    # SwingTime — Denver
    37: 195,   # Palm Springs New Year — Palm Springs
    193: 236,  # Warsaw Halloween Swing — Warsaw
    99: 119,   # Chicagoland Dance Festival — Chicago
    198: 154,  # UK WCS — London
    202: 218,  # Asia WCS Open — Singapore
    39: 334,   # Countdown Swing Boston — Boston/Framingham metro
    307: 272,  # Paris Westie Fest — Paris
    543: 272,  # Paris Swing Classic ghost / inactive → Paris Westie Fest
    325: 330,  # Simply Adelaide — Adelaide
    321: 331,  # Swing Fiction — Brno
    279: 283,  # Kazan EL Fest — Kazan
    406: 197,  # 5280 Championships ghost → 5280 Westival
    433: 369,  # French Connection WCS casing duplicate → FRENCH CONNECTION WCS
    442: 120,  # Lonestar ghost → Lone Star Invitational
    566: 9,    # The Boston Tea Party inactive → Boston Tea Party
    506: 12,   # Capital Swing Convention inactive → Capital Swing Dance Convention
    571: 179,  # NZ WCS Open inactive → New Zealand Open Swing Dance Championships
    412: 374,  # BaroqueSwing ghost → Barock Swing Ludwigsburg
    493: 264,  # UpTown Swing catalog ghost → Swedish/UpTown series (results on 264)
    551: 221,  # Show Me Showdown inactive → id reused by Gateway (results on 221)
    552: 221,  # Show-Me Showdown spelling ghost → 221
    467: 221,  # Orphan calendar match for Show Me Showdown → 221
    # NOTE: id 443 was once a LoneStar ghost; WSDC reused it for MADjam phantom
    # (see PHANTOM_ALIAS_TO_CANONICAL 443→92). Do not map 443→120.
}

# Year-aware series renames (same organizer/geo, marketing rebrand / WSDC id reuse).
# Applied after flat EVENT_NAME_NORMALIZATION. Sources match either legacy or modern title.
# year_max inclusive for early name; year_min inclusive for late name.
# Prefer one stable results id for the whole series; display name follows the year.
EVENT_NAME_YEAR_SPLITS: list[dict[str, object]] = [
    {
        "sources": (
            "Swedish Swing Summer Camp",
            "UpTown Swing",
            "Uptown Swing",
        ),
        "early_name": "Swedish Swing Summer Camp",
        "early_year_max": 2018,
        "late_name": "UpTown Swing",
        "late_year_min": 2019,
        # Results live on 264 for all years; 493 is a catalog/schedule ghost (merged).
        "early_event_id": 264,
        "late_event_id": 264,
    },
    {
        "sources": (
            "Show Me Showdown",
            "Show-Me Showdown",
            "Gateway Swing Classic",
        ),
        "early_name": "Show Me Showdown",
        "early_year_max": 2025,
        "late_name": "Gateway Swing Classic",
        "late_year_min": 2026,
        # WSDC reused registry id 221 (Show Me history → Gateway from 2026).
        "early_event_id": 221,
        "late_event_id": 221,
    },
]


def apply_event_name_year_splits(df: pd.DataFrame) -> pd.DataFrame:
    """Rename event by edition year for known rebranded series.

    Supports results (`event_name`) and events_wsdc (`name` + `id`).
    """
    if df is None or df.empty or "event_year" not in df.columns:
        return df
    name_col = (
        "event_name"
        if "event_name" in df.columns
        else ("name" if "name" in df.columns else None)
    )
    if name_col is None:
        return df

    out = df.copy()
    years = pd.to_numeric(out["event_year"], errors="coerce")
    names = out[name_col].astype(str).str.strip()
    id_col = (
        "event_name_id"
        if "event_name_id" in out.columns
        else ("id" if "id" in out.columns else None)
    )

    for rule in EVENT_NAME_YEAR_SPLITS:
        sources = {str(s).strip() for s in rule["sources"]}  # type: ignore[arg-type]
        mask_src = names.isin(sources)
        if not mask_src.any():
            continue
        early_max = int(rule["early_year_max"])  # type: ignore[arg-type]
        late_min = int(rule["late_year_min"])  # type: ignore[arg-type]
        early_name = str(rule["early_name"])
        late_name = str(rule["late_name"])

        early = mask_src & years.notna() & (years <= early_max)
        late = mask_src & years.notna() & (years >= late_min)
        out.loc[early, name_col] = early_name
        out.loc[late, name_col] = late_name

        if id_col is not None:
            early_id = rule.get("early_event_id")
            late_id = rule.get("late_event_id")
            if early_id is not None:
                assign_column_values(out, id_col, early, int(early_id))
            if late_id is not None:
                assign_column_values(out, id_col, late, int(late_id))

    return out


def build_event_name_normalization() -> dict[str, str]:
    """Single preprocess map: every key resolves to a core.events.name."""
    merged: dict[str, str] = {}
    merged.update(EVENT_NAME_VARIANT_TO_CATALOG)
    merged.update(RESULT_TO_CATALOG_EVENT_NAME)
    return merged

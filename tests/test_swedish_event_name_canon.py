"""Swedish series naming: Westie Gala canon + SSSC/UpTown year split."""

import pandas as pd

from transform.knowledge.event_aliases import (
    apply_event_name_year_splits,
    build_event_name_normalization,
)
from transform.knowledge.events import (
    EVENT_NAME_LOCATION_OVERRIDES,
    EVENT_NAME_NORMALIZATION,
    EVENT_NAME_YEAR_LOCATION_OVERRIDES,
    KNOWN_EVENT_METADATA,
)


def test_westie_gala_is_canonical_alias_target():
    norm = build_event_name_normalization()
    assert norm["Sweden Westie Gala"] == "Westie Gala"
    assert norm["Vestigala"] == "Westie Gala"
    assert norm["Westigala"] == "Westie Gala"
    assert "UpTown Swing" not in norm  # must not collapse into SSSC


def test_westie_gala_metadata_and_stockholm_override():
    assert KNOWN_EVENT_METADATA[240]["name"] == "Westie Gala"
    assert EVENT_NAME_LOCATION_OVERRIDES["Westie Gala"] == "Stockholm, Sweden"
    assert EVENT_NAME_LOCATION_OVERRIDES["Valentine Swing"] == "Stockholm, Sweden"
    assert EVENT_NAME_LOCATION_OVERRIDES["UpTown Swing"] == "Stockholm, Sweden"
    assert EVENT_NAME_LOCATION_OVERRIDES["Revitalise WCS"] == "Melbourne, Australia"
    assert EVENT_NAME_LOCATION_OVERRIDES["Montreal Westie Fest"] == "Montreal, Canada"
    assert KNOWN_EVENT_METADATA[178]["typical_location"] == "Montreal, Canada"
    assert EVENT_NAME_LOCATION_OVERRIDES["Korea Westival"] == "Jeju, Republic of Korea"
    assert EVENT_NAME_LOCATION_OVERRIDES["Warsaw Summer Nights Westival"] == "Warsaw, Poland"
    assert EVENT_NAME_LOCATION_OVERRIDES["Mooseland Swing"] == "Östersund, Sweden"
    assert (
        EVENT_NAME_YEAR_LOCATION_OVERRIDES[("Go West SwingFest", 2019, 2019)]
        == "Fremantle, Australia"
    )
    assert (
        EVENT_NAME_YEAR_LOCATION_OVERRIDES[("Go West SwingFest", 2024, 2099)]
        == "Perth, Australia"
    )
    assert (
        EVENT_NAME_YEAR_LOCATION_OVERRIDES[("Sunny Side Dance Camp", 2012, 2013)]
        == "Crimea, Ukraine"
    )
    assert (
        EVENT_NAME_YEAR_LOCATION_OVERRIDES[("Sunny Side Dance Camp", 2014, 2099)]
        == "Torrevieja, Spain"
    )
    assert EVENT_NAME_LOCATION_OVERRIDES["New Zealand Open Swing Dance Championships"] == "Auckland, New Zealand"
    assert EVENT_NAME_LOCATION_OVERRIDES["DC Swing eXperience (DCSX)"] == "Herndon, VA, United States"
    assert (
        EVENT_NAME_LOCATION_OVERRIDES["Dance Jam Jack & Jill Weekend"]
        == "Silver Spring, MD, United States"
    )
    assert KNOWN_EVENT_METADATA[372]["typical_location"] == "Silver Spring, MD, United States"
    assert (
        EVENT_NAME_LOCATION_OVERRIDES[
            "Waterloo Ontario Open West Coast Swing Championships"
        ]
        == "Waterloo, Canada"
    )
    assert KNOWN_EVENT_METADATA[387]["typical_location"] == "Waterloo, Canada"
    assert EVENT_NAME_LOCATION_OVERRIDES["Euro Dance Festival"] == "Rust, Germany"
    assert EVENT_NAME_LOCATION_OVERRIDES["Barock Swing Ludwigsburg"] == "Ludwigsburg, Germany"
    assert EVENT_NAME_LOCATION_OVERRIDES["Infinite Swing"] == "Munich, Germany"
    assert KNOWN_EVENT_METADATA[404]["typical_location"] == "Munich, Germany"
    assert EVENT_NAME_LOCATION_OVERRIDES["Swingsation"] == "Gold Coast, Australia"
    assert KNOWN_EVENT_METADATA[174]["typical_location"] == "Gold Coast, Australia"
    assert EVENT_NAME_LOCATION_OVERRIDES["SwingVester"] == "Wels, Austria"
    assert KNOWN_EVENT_METADATA[289]["typical_location"] == "Wels, Austria"
    assert KNOWN_EVENT_METADATA[289]["url"] == "https://www.swingvester.com/"
    assert EVENT_NAME_LOCATION_OVERRIDES["Rock the Barn"] == "Umeå, Sweden"
    assert EVENT_NAME_LOCATION_OVERRIDES["Rock The Barn"] == "Umeå, Sweden"
    assert KNOWN_EVENT_METADATA[256]["typical_location"] == "Umeå, Sweden"
    assert EVENT_NAME_LOCATION_OVERRIDES["WCS Party"] == "Vienna, Austria"
    assert EVENT_NAME_LOCATION_OVERRIDES["WCS Party in Vienna"] == "Vienna, Austria"
    assert KNOWN_EVENT_METADATA[357]["typical_location"] == "Vienna, Austria"
    assert EVENT_NAME_LOCATION_OVERRIDES["Southern Lights Swing"] == "Hobart, Australia"
    assert EVENT_NAME_LOCATION_OVERRIDES["Countdown Swing Boston"] == "Boston, MA, United States"
    assert EVENT_NAME_LOCATION_OVERRIDES["Summer Hummer"] == "Woburn (Boston), MA, United States"
    assert (
        EVENT_NAME_LOCATION_OVERRIDES["New England Dance Festival"]
        == "Newton (Boston), MA, United States"
    )
    assert (
        EVENT_NAME_LOCATION_OVERRIDES["New Year's Dancin' Eve"]
        == "Burlington (Boston), MA, United States"
    )
    assert (
        EVENT_NAME_YEAR_LOCATION_OVERRIDES[("Countdown Swing Boston", 2025, 2099)]
        == "Mansfield (Boston), MA, United States"
    )
    assert KNOWN_EVENT_METADATA[394]["typical_location"] == "Hobart, Australia"
    assert (
        EVENT_NAME_YEAR_LOCATION_OVERRIDES[
            ("Global Grand Prix - West Coast Swing Reunion", 2026, 2099)
        ]
        == "Paris, France"
    )


def test_year_split_sssc_vs_uptown_results():
    df = pd.DataFrame(
        [
            {"event_name": "Swedish Swing Summer Camp", "event_year": 2017},
            {"event_name": "Swedish Swing Summer Camp", "event_year": 2019},
            {"event_name": "UpTown Swing", "event_year": 2018},
            {"event_name": "UpTown Swing", "event_year": 2024},
        ]
    )
    out = apply_event_name_year_splits(df)
    assert out.loc[0, "event_name"] == "Swedish Swing Summer Camp"
    assert out.loc[1, "event_name"] == "UpTown Swing"
    assert out.loc[2, "event_name"] == "Swedish Swing Summer Camp"
    assert out.loc[3, "event_name"] == "UpTown Swing"


def test_year_split_events_wsdc_ids():
    df = pd.DataFrame(
        [
            {"id": 264, "name": "Swedish Swing Summer Camp", "event_year": 2016},
            {"id": 264, "name": "Swedish Swing Summer Camp", "event_year": 2023},
        ]
    )
    out = apply_event_name_year_splits(df)
    assert int(out.loc[0, "id"]) == 264
    assert out.loc[0, "name"] == "Swedish Swing Summer Camp"
    assert int(out.loc[1, "id"]) == 264
    assert out.loc[1, "name"] == "UpTown Swing"


def test_year_split_ids_on_string_dtype_frame():
    # Preprocess loads CSVs with dtype=str; pandas 3 rejects int into a str column.
    df = pd.DataFrame(
        [
            {"id": "264", "name": "Swedish Swing Summer Camp", "event_year": "2016"},
            {"id": "264", "name": "Swedish Swing Summer Camp", "event_year": "2023"},
        ]
    ).astype("str")
    out = apply_event_name_year_splits(df)
    assert out.loc[0, "id"] == "264"
    assert out.loc[1, "id"] == "264"
    assert out.loc[1, "name"] == "UpTown Swing"


def test_year_split_show_me_vs_gateway():
    df = pd.DataFrame(
        [
            {"event_name": "Show Me Showdown", "event_year": 2025, "event_name_id": 221},
            {"event_name": "Gateway Swing Classic", "event_year": 2025, "event_name_id": 221},
            {"event_name": "Show Me Showdown", "event_year": 2026, "event_name_id": 221},
            {"event_name": "Gateway Swing Classic", "event_year": 2026, "event_name_id": 221},
        ]
    )
    out = apply_event_name_year_splits(df)
    assert out.loc[0, "event_name"] == "Show Me Showdown"
    assert out.loc[1, "event_name"] == "Show Me Showdown"
    assert out.loc[2, "event_name"] == "Gateway Swing Classic"
    assert out.loc[3, "event_name"] == "Gateway Swing Classic"
    assert int(out.loc[0, "event_name_id"]) == 221
    assert int(out.loc[3, "event_name_id"]) == 221


def test_uptown_and_show_me_ghosts_merge_to_results_ids():
    from transform.knowledge.event_aliases import MERGE_EVENT_ID_MAP

    assert MERGE_EVENT_ID_MAP[493] == 264
    assert MERGE_EVENT_ID_MAP[551] == 221
    assert MERGE_EVENT_ID_MAP[552] == 221
    assert MERGE_EVENT_ID_MAP[467] == 221


def test_normalization_map_exports_westie_gala():
    # Shared preprocess map must match alias builder.
    assert EVENT_NAME_NORMALIZATION["Sweden Westie Gala"] == "Westie Gala"

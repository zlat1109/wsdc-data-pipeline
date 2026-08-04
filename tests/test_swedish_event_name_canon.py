"""Swedish series naming: Westie Gala canon + SSSC/UpTown year split."""

import pandas as pd

from transform.knowledge.event_aliases import (
    apply_event_name_year_splits,
    build_event_name_normalization,
)
from transform.knowledge.events import (
    EVENT_NAME_LOCATION_OVERRIDES,
    EVENT_NAME_NORMALIZATION,
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
    assert EVENT_NAME_LOCATION_OVERRIDES["Korea Westival"] == "Jeju, Republic of Korea"
    assert EVENT_NAME_LOCATION_OVERRIDES["Warsaw Summer Nights Westival"] == "Warsaw, Poland"
    assert EVENT_NAME_LOCATION_OVERRIDES["Mooseland Swing"] == "Östersund, Sweden"
    assert EVENT_NAME_LOCATION_OVERRIDES["Go West SwingFest"] == "Perth, Australia"
    assert EVENT_NAME_LOCATION_OVERRIDES["New Zealand Open Swing Dance Championships"] == "Auckland, New Zealand"
    assert EVENT_NAME_LOCATION_OVERRIDES["DC Swing eXperience (DCSX)"] == "Herndon, VA, United States"
    assert (
        EVENT_NAME_LOCATION_OVERRIDES["Dance Jam Jack & Jill Weekend"]
        == "Silver Spring, MD, United States"
    )
    assert KNOWN_EVENT_METADATA[372]["typical_location"] == "Silver Spring, MD, United States"


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

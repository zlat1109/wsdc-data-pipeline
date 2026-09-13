"""Guards against the LOCATION_ID_MERGE_MAP hijack of freshly minted location_ids.

Root cause of every "shared wrong location_id" incident (São Paulo 243, St. Petersburg
222, Brno 266, Perth 253, Wailea 124, …): resolve_result_location_ids minted
max(registry)+1 for an unknown WSDC string, and consolidate_location_ids then remapped
that id through a *retired* merge-map key (398 → 243, 401 → 222, 412 → 266).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from transform.geography.resolve import (
    LOCATION_COLUMNS,
    city_country_fallback_key,
    consolidate_location_ids,
    dedupe_location_info,
    resolve_result_location_ids,
    retired_location_ids,
)
from transform.knowledge.locations import LOCATION_ID_CORRECTIONS, LOCATION_ID_MERGE_MAP

REGISTRY_CSV = Path(__file__).resolve().parents[1] / "data" / "location_info.csv"


def _loc(location_id: str, city: str, country: str, state: str = "") -> dict[str, str]:
    text = ", ".join(p for p in (city, state, country) if p)
    return {
        "location_id": location_id,
        "event_city": city,
        "event_state": state,
        "event_country": country,
        "latitude": "",
        "longitude": "",
        "event_location": text,
        "event_location_standardized": text,
        "coordinates_valid": "",
    }


def _registry_below_retired_ids() -> pd.DataFrame:
    """Small registry whose max id sits just below the lowest retired merge key."""
    retired = sorted(retired_location_ids())
    assert retired, "LOCATION_ID_MERGE_MAP must not be empty for this guard"
    first_retired = retired[0]
    rows = [
        _loc(str(first_retired - 1), "São Paulo", "Brazil"),
        _loc(str(first_retired - 2), "Incheon", "Republic of Korea"),
    ]
    return pd.DataFrame(rows).reindex(columns=LOCATION_COLUMNS, fill_value="")


def test_retired_ids_cover_merge_map_and_corrections_keys():
    expected = {int(k) for k in LOCATION_ID_MERGE_MAP} | {int(k) for k in LOCATION_ID_CORRECTIONS}
    assert retired_location_ids() == frozenset(expected)


@pytest.mark.skipif(not REGISTRY_CSV.exists(), reason="committed registry not available")
def test_every_corrections_key_exists_in_committed_registry():
    """A CORRECTIONS key without a registry row is a dangling id-keyed patch.

    If such a row is ever merged/deduped away, the patch must be deleted (or the id
    added to LOCATION_ID_MERGE_MAP) — otherwise export.py would paint a future
    city with the old coordinates.
    """
    registry = pd.read_csv(REGISTRY_CSV, dtype=str, usecols=["location_id"])
    present = {int(v) for v in registry["location_id"].dropna()}
    dangling = sorted(int(k) for k in LOCATION_ID_CORRECTIONS if int(k) not in present)
    assert not dangling, f"LOCATION_ID_CORRECTIONS keys missing from location_info.csv: {dangling}"


@pytest.mark.skipif(not REGISTRY_CSV.exists(), reason="committed registry not available")
def test_no_merge_map_key_survives_in_committed_registry():
    """Merge keys are retired ids; a live row on one means the merge never ran."""
    registry = pd.read_csv(REGISTRY_CSV, dtype=str, usecols=["location_id"])
    present = {str(v).strip() for v in registry["location_id"].dropna()}
    alive = sorted(k for k in LOCATION_ID_MERGE_MAP if k in present)
    assert not alive, f"LOCATION_ID_MERGE_MAP keys still present in location_info.csv: {alive}"


def test_fresh_location_id_never_reuses_a_retired_merge_key():
    registry = _registry_below_retired_ids()
    unknown = [f"Town{i}, Region, Estonia" for i in range(60)]
    results = pd.DataFrame(
        [{"event_name": f"Event {i}", "location_id": "", "event_location": raw} for i, raw in enumerate(unknown)]
    )

    out, _ = resolve_result_location_ids(results, registry)
    minted = {int(v) for v in out["location_id"]}

    assert minted.isdisjoint(retired_location_ids()), sorted(minted & retired_location_ids())
    assert len(minted) == len(unknown)


def test_consolidate_after_resolve_cannot_hijack_a_fresh_city():
    """End-to-end: unknown Estonian town must not end up on São Paulo / St. Pete / Brno."""
    registry = _registry_below_retired_ids()
    results = pd.DataFrame(
        [{"event_name": "Brand New Event", "location_id": "", "event_location": "Tartu, Tartumaa, Estonia"}]
    )

    resolved, locations = resolve_result_location_ids(results, registry)
    merged, merged_locs = consolidate_location_ids(resolved, locations)
    final, _, _ = dedupe_location_info(merged, merged_locs)

    lid = str(final.loc[0, "location_id"])
    first_retired = min(retired_location_ids())
    expected = first_retired + 1
    while expected in retired_location_ids():
        expected += 1
    assert lid == str(expected), f"fresh city expected id {expected}, got {lid} (hijacked?)"
    assert lid not in set(LOCATION_ID_MERGE_MAP.values())


def test_three_part_wsdc_string_matches_two_part_registry_row():
    """WSDC 'City, Region, Country' resolves to the existing 'City, Country' row."""
    registry = pd.DataFrame(
        [
            _loc("172", "Incheon", "Republic of Korea"),
            _loc("204", "Helsinki", "Finland"),
            _loc("191", "Amsterdam", "Netherlands"),
            _loc("243", "São Paulo", "Brazil"),
        ]
    ).reindex(columns=LOCATION_COLUMNS, fill_value="")
    results = pd.DataFrame(
        [
            {"event_name": "Korean Open WCS Championships", "location_id": "", "event_location": "Incheon, Incheon, South Korea"},
            {"event_name": "Finnfest", "location_id": "", "event_location": "Helsinki, Uusimaa, Finland"},
            {"event_name": "Neverland Swing", "location_id": "", "event_location": "Amsterdam, North Holland, Netherlands"},
        ]
    )

    out, out_locs = resolve_result_location_ids(results, registry)

    assert out["location_id"].tolist() == ["172", "204", "191"]
    assert len(out_locs) == len(registry), "no duplicate registry rows should be created"


def test_city_country_fallback_skips_us_and_short_strings():
    assert city_country_fallback_key("Incheon, Incheon, South Korea") == "incheon, republic of korea"
    assert city_country_fallback_key("Ottawa, Ontario, Canada") == "ottawa, canada"
    assert city_country_fallback_key("Boston, MA, United States") == ""
    assert city_country_fallback_key("Helsinki, Finland") == ""
    assert city_country_fallback_key("") == ""

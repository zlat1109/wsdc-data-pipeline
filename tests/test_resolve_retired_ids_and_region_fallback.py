"""Guards against the LOCATION_ID_MERGE_MAP hijack of freshly minted location_ids.

Root cause of every "shared wrong location_id" incident (São Paulo 243, St. Petersburg
222, Brno 266, Perth 253, Wailea 124, …): resolve_result_location_ids minted
max(registry)+1 for an unknown WSDC string, and consolidate_location_ids then remapped
that id through a *retired* merge-map key (398 → 243, 401 → 222, 412 → 266).
"""

from __future__ import annotations

import pandas as pd

from transform.geography.resolve import (
    LOCATION_COLUMNS,
    city_country_fallback_key,
    consolidate_location_ids,
    dedupe_location_info,
    resolve_result_location_ids,
    retired_location_ids,
)
from transform.knowledge.locations import LOCATION_ID_MERGE_MAP


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


def test_retired_ids_cover_every_merge_map_key():
    assert retired_location_ids() == frozenset(int(k) for k in LOCATION_ID_MERGE_MAP)


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
    assert lid not in set(LOCATION_ID_MERGE_MAP.values()), f"fresh city hijacked onto {lid}"
    assert lid not in LOCATION_ID_MERGE_MAP


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

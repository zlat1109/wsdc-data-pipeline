"""Apply MERGE_EVENT_ID_MAP to event id columns (preprocess ingest path)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from transform.knowledge.event_aliases import MERGE_EVENT_ID_MAP

if TYPE_CHECKING:
    from transform.preprocess_tracker import PreprocessTracker


def apply_merge_event_id_map(
    df: pd.DataFrame,
    *,
    column: str = "event_name_id",
    merge_map: dict[int, int] | None = None,
    tracker: PreprocessTracker | None = None,
    table: str = "dancers_results_info",
) -> pd.DataFrame:
    """Remap duplicate WSDC registry ids to canonical event_id before load.

    Preprocess path: map is pre-vetted in event_aliases.py (no runtime geo gate).
    Existing DB rows: use scripts/merge_event_ids.py (geo gate + core.results UPDATE).
    """
    mapping = merge_map if merge_map is not None else MERGE_EVENT_ID_MAP
    if column not in df.columns or not mapping:
        return df

    out = df.copy()
    ids = pd.to_numeric(out[column], errors="coerce")
    for source_id, canonical_id in mapping.items():
        mask = ids == source_id
        count = int(mask.sum())
        if not count:
            continue
        if tracker is not None:
            tracker.record(
                "MERGE_EVENT_ID_MAP",
                table,
                column,
                str(source_id),
                str(canonical_id),
                count,
                "known_map",
            )
        out.loc[mask, column] = canonical_id
        ids = pd.to_numeric(out[column], errors="coerce")
    return out

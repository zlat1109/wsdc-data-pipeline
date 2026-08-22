"""CSV-side edition location baseline drift check (pre-load early signal)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class CsvBaselineDrift:
    event_id: str
    event_year: str
    event_month: str
    event_name: str
    baseline_location_id: str
    current_location_id: str
    result_rows: int


def _mode_location_id(frame: pd.DataFrame) -> str:
    if frame.empty or "location_id" not in frame.columns:
        return ""
    counts = frame["location_id"].astype(str).str.strip().value_counts()
    counts = counts[counts.index != ""]
    if counts.empty:
        return ""
    return str(counts.index[0])


def find_csv_baseline_drifts(
    results: pd.DataFrame,
    baseline: pd.DataFrame,
) -> list[CsvBaselineDrift]:
    """Compare results mode location_id per edition key against exported baseline CSV."""
    if results is None or results.empty or baseline is None or baseline.empty:
        return []

    id_col = "event_name_id" if "event_name_id" in results.columns else None
    if id_col is None or "event_year" not in results.columns or "event_month" not in results.columns:
        return []
    if "location_id" not in results.columns:
        return []

    req = {"event_id", "event_year", "event_month", "location_id"}
    if not req.issubset(set(baseline.columns)):
        return []

    base = baseline.copy()
    for col in ("event_id", "event_year", "event_month", "location_id"):
        base[col] = base[col].astype(str).str.strip()
    base = base[base["event_id"] != ""]
    base_lookup = {
        (r["event_id"], r["event_year"], r["event_month"]): r["location_id"]
        for _, r in base.iterrows()
    }

    res = results.copy()
    res["_eid"] = res[id_col].astype(str).str.strip()
    res["_year"] = pd.to_numeric(res["event_year"], errors="coerce")
    res["_month"] = pd.to_numeric(res["event_month"], errors="coerce")
    res = res[res["_eid"] != ""]
    res = res.dropna(subset=["_year", "_month"])

    name_col = "event_name" if "event_name" in res.columns else None
    out: list[CsvBaselineDrift] = []

    grouped = res.groupby(["_eid", "_year", "_month"], dropna=False)
    for (eid, year, month), grp in grouped:
        key = (str(int(eid)) if str(eid).isdigit() else str(eid), str(int(year)), str(int(month)))
        expected = base_lookup.get(key)
        if not expected:
            continue
        current = _mode_location_id(grp)
        if not current or current == expected:
            continue
        event_name = ""
        if name_col:
            modes = grp[name_col].astype(str).str.strip().value_counts()
            if not modes.empty:
                event_name = str(modes.index[0])
        out.append(
            CsvBaselineDrift(
                event_id=key[0],
                event_year=key[1],
                event_month=key[2],
                event_name=event_name,
                baseline_location_id=expected,
                current_location_id=current,
                result_rows=int(len(grp)),
            )
        )

    out.sort(key=lambda d: (d.event_year, d.event_month, d.event_name), reverse=True)
    return out

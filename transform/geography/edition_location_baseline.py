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


@dataclass(frozen=True)
class CsvBaselineOverrideConflict:
    """Baseline frozen a location that disagrees with EVENT_NAME_LOCATION_OVERRIDES.

    Cross-load drift only fires when *current* ≠ baseline. If seed/auto-add froze
    an already-wrong shared location_id, both stay equal and drift stays silent —
    this check catches that poison-seed case.
    """

    event_id: str
    event_year: str
    event_month: str
    event_name: str
    baseline_location_id: str
    override_location_id: str
    override_location: str


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


def find_baseline_override_conflicts(
    baseline: pd.DataFrame,
    location_info: pd.DataFrame,
    *,
    name_overrides: dict[str, str] | None = None,
    year_overrides: dict | None = None,
    resolve_location_id=None,
) -> list[CsvBaselineOverrideConflict]:
    """Flag baseline rows whose location_id conflicts with a name override target.

    Uses flat ``EVENT_NAME_LOCATION_OVERRIDES`` then year-scoped
    ``EVENT_NAME_YEAR_LOCATION_OVERRIDES`` (same order as force_result_locations).

    ``resolve_location_id(target_text) -> location_id|None`` should use the same
    lookup as force_result_locations (optional; falls back to exact event_location).
    """
    if baseline is None or baseline.empty or location_info is None or location_info.empty:
        return []
    if name_overrides is None or year_overrides is None:
        from transform.knowledge.events import (
            EVENT_NAME_LOCATION_OVERRIDES,
            EVENT_NAME_YEAR_LOCATION_OVERRIDES,
        )

        if name_overrides is None:
            name_overrides = EVENT_NAME_LOCATION_OVERRIDES
        if year_overrides is None:
            year_overrides = EVENT_NAME_YEAR_LOCATION_OVERRIDES
    if not name_overrides and not year_overrides:
        return []

    req = {"event_id", "event_year", "event_month", "location_id", "event_name"}
    if not req.issubset(set(baseline.columns)):
        return []

    loc = location_info.copy()
    loc["location_id"] = loc["location_id"].astype(str).str.strip()
    by_exact: dict[str, str] = {}
    country_by_lid: dict[str, str] = {}
    if "event_country" in loc.columns:
        for _, row in loc.iterrows():
            lid = str(row.get("location_id") or "").strip()
            country = str(row.get("event_country") or "").strip().lower()
            if lid and country:
                country_by_lid[lid] = country
    if "event_location" in loc.columns:
        for _, row in loc.iterrows():
            text = str(row.get("event_location") or "").strip()
            lid = str(row.get("location_id") or "").strip()
            if text and lid:
                by_exact[text.lower()] = lid
    if "event_location_standardized" in loc.columns:
        for _, row in loc.iterrows():
            text = str(row.get("event_location_standardized") or "").strip()
            lid = str(row.get("location_id") or "").strip()
            if text and lid and text.lower() not in by_exact:
                by_exact[text.lower()] = lid

    def _resolve(target: str) -> str | None:
        if resolve_location_id is not None:
            got = resolve_location_id(target)
            if got:
                return str(got).strip()
        return by_exact.get(str(target).strip().lower())

    def _target_for(name: str, year: int | None) -> str | None:
        target = name_overrides.get(name) if name_overrides else None
        if year is None:
            return target
        for (n, y0, y1), loc_text in (year_overrides or {}).items():
            if n == name and y0 <= year <= y1:
                return loc_text
        return target

    def _country(lid: str) -> str:
        return country_by_lid.get(lid, "")

    out: list[CsvBaselineOverrideConflict] = []
    base = baseline.copy()
    for col in ("event_id", "event_year", "event_month", "location_id", "event_name"):
        base[col] = base[col].astype(str).str.strip()

    for _, row in base.iterrows():
        name = row["event_name"]
        try:
            year_i = int(float(row["event_year"]))
        except (TypeError, ValueError):
            year_i = None
        target = _target_for(name, year_i)
        if not target:
            continue
        want = _resolve(target)
        if not want:
            continue
        got = row["location_id"]
        if not got or got == want:
            continue
        # Same-country suburb/metro differences (Boston Framingham vs Boston) are
        # not poison seeds — only cross-country shared-lid collisions.
        got_c, want_c = _country(got), _country(want)
        if got_c and want_c and got_c == want_c:
            continue
        out.append(
            CsvBaselineOverrideConflict(
                event_id=row["event_id"],
                event_year=row["event_year"],
                event_month=row["event_month"],
                event_name=name,
                baseline_location_id=got,
                override_location_id=want,
                override_location=str(target),
            )
        )

    out.sort(key=lambda d: (d.event_year, d.event_month, d.event_name), reverse=True)
    return out

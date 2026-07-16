"""Match normalized calendar rows to event_editions / event_catalog."""

from __future__ import annotations

from typing import Any

import pandas as pd

from transform.events_calendar_normalize import host_key, name_key
from transform.events_list_normalize import normalize_url
from transform.knowledge.event_aliases import (
    EVENT_NAME_VARIANT_TO_CATALOG,
    RESULT_TO_CATALOG_EVENT_NAME,
)


def _edition_name_key(name: str) -> str:
    return name_key(str(name or ""))


def _build_url_to_event_ids(catalog: pd.DataFrame) -> dict[str, list[str]]:
    """Map normalized URL / host → candidate event_ids (URL collisions kept)."""
    if catalog.empty or "url" not in catalog.columns:
        return {}
    out: dict[str, list[str]] = {}
    for _, row in catalog.iterrows():
        eid = str(row.get("event_id") or "").strip()
        if not eid:
            continue
        keys = []
        uk = normalize_url(str(row.get("url") or ""))
        if uk:
            keys.append(uk)
        hk = host_key(str(row.get("url") or ""))
        if hk:
            keys.append(f"host:{hk}")
        for key in keys:
            bucket = out.setdefault(key, [])
            if eid not in bucket:
                bucket.append(eid)
    return out


def _pick_event_id(
    candidates: list[str],
    *,
    name_key_val: str,
    ym_pairs: list[tuple[int, int]],
    ed_by_id_ym: dict[tuple[str, int, int], dict],
    name_map: dict[str, str],
) -> str:
    if not candidates:
        return ""
    if len(candidates) == 1:
        return candidates[0]
    # Prefer id that has an edition in candidate year/months.
    for eid in candidates:
        for y, m in ym_pairs:
            if (eid, y, m) in ed_by_id_ym:
                return eid
    # Prefer id whose catalog/edition name matches calendar name_key.
    if name_key_val and name_map.get(name_key_val) in candidates:
        return name_map[name_key_val]
    return candidates[0]


def _build_name_to_event_id(catalog: pd.DataFrame, editions: pd.DataFrame) -> dict[str, str]:
    out: dict[str, str] = {}
    alias_low = {
        **{k.lower(): v for k, v in RESULT_TO_CATALOG_EVENT_NAME.items()},
        **{k.lower(): v for k, v in EVENT_NAME_VARIANT_TO_CATALOG.items()},
    }

    def _register(name: str, event_id: str) -> None:
        if not name or not event_id:
            return
        nk = _edition_name_key(name)
        if nk and nk not in out:
            out[nk] = event_id
        canon = alias_low.get(name.lower(), name)
        ck = _edition_name_key(canon)
        if ck and ck not in out:
            out[ck] = event_id

    if not catalog.empty:
        for _, row in catalog.iterrows():
            _register(str(row.get("canonical_name") or ""), str(row.get("event_id") or ""))
    if not editions.empty:
        for _, row in editions.drop_duplicates(["event_id", "event_name"]).iterrows():
            _register(str(row.get("event_name") or ""), str(row.get("event_id") or ""))
    return out


def match_calendar_to_editions(
    calendar_rows: list[dict[str, Any]],
    editions: pd.DataFrame,
    catalog: pd.DataFrame | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Attach event_id / edition_id when calendar row matches an edition."""
    cat = catalog if catalog is not None else pd.DataFrame()
    ed = editions.copy()
    if ed.empty:
        return [], {"matched": 0, "unmatched": len(calendar_rows), "total": len(calendar_rows)}

    ed["event_id"] = ed["event_id"].astype(str)
    ed["event_year"] = ed["event_year"].astype(int)
    ed["event_month"] = ed["event_month"].astype(int)
    ed["name_key"] = ed["event_name"].map(_edition_name_key)
    ed_by_id_ym: dict[tuple[str, int, int], dict[str, Any]] = {}
    for _, row in ed.iterrows():
        key = (str(row["event_id"]), int(row["event_year"]), int(row["event_month"]))
        ed_by_id_ym[key] = row.to_dict()

    url_map = _build_url_to_event_ids(cat)
    name_map = _build_name_to_event_id(cat, ed)

    matched_rows: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []

    for cal in calendar_rows:
        event_id = ""
        match_via = ""
        nk = cal.get("name_key") or ""
        ym_pairs: list[tuple[int, int]] = []
        for ym in cal.get("edition_ym_candidates") or []:
            y_s, m_s = ym.split("-")
            ym_pairs.append((int(y_s), int(m_s)))

        uk = cal.get("url_key") or ""
        if uk and uk in url_map:
            event_id = _pick_event_id(
                url_map[uk],
                name_key_val=nk,
                ym_pairs=ym_pairs,
                ed_by_id_ym=ed_by_id_ym,
                name_map=name_map,
            )
            match_via = "url"
        if not event_id:
            hk = host_key(cal.get("url") or "")
            if hk and f"host:{hk}" in url_map:
                event_id = _pick_event_id(
                    url_map[f"host:{hk}"],
                    name_key_val=nk,
                    ym_pairs=ym_pairs,
                    ed_by_id_ym=ed_by_id_ym,
                    name_map=name_map,
                )
                match_via = "url_host"
        if not event_id and nk and nk in name_map:
            event_id = name_map[nk]
            match_via = "name"

        edition = None
        for y, m in ym_pairs:
            if event_id:
                edition = ed_by_id_ym.get((event_id, y, m))
            if edition is None:
                hits = ed[(ed["name_key"] == nk) & (ed["event_year"] == y) & (ed["event_month"] == m)]
                if len(hits) == 1:
                    edition = hits.iloc[0].to_dict()
                    event_id = str(edition["event_id"])
                    match_via = match_via or "name_ym"
            if edition is not None:
                break

        matched_year = ""
        matched_month = ""
        if edition:
            matched_year = str(edition.get("event_year") or "")
            matched_month = str(edition.get("event_month") or "")
        row = {
            **cal,
            "matched_event_id": event_id or "",
            "matched_edition_id": str(edition.get("edition_id") or "") if edition else "",
            "matched_event_name": str(edition.get("event_name") or "") if edition else "",
            "matched_event_year": matched_year,
            "matched_event_month": matched_month,
            "match_via": match_via if edition else (match_via if event_id else ""),
            "match_status": "matched" if edition else ("event_only" if event_id else "unmatched"),
        }
        if edition:
            matched_rows.append(row)
        else:
            unmatched.append(row)

    summary = {
        "total": len(calendar_rows),
        "matched": len(matched_rows),
        "event_only": sum(1 for r in unmatched if r["match_status"] == "event_only"),
        "unmatched": sum(1 for r in unmatched if r["match_status"] == "unmatched"),
        "by_via": {},
    }
    for r in matched_rows:
        via = r.get("match_via") or "unknown"
        summary["by_via"][via] = summary["by_via"].get(via, 0) + 1

    return matched_rows + unmatched, summary

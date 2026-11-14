"""Build officials dim + edition_officials bridge from Todd Results Form fields."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd


def normalize_person_name(name: str | None) -> str:
    if not name:
        return ""
    s = re.sub(r"\s+", " ", name.strip().lower())
    s = s.replace(".", "")
    return s


def _as_list(v: Any) -> list[str]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    # duckdb/pandas may give ndarray
    try:
        return [str(x).strip() for x in list(v) if str(x).strip()]
    except TypeError:
        return []


def build_officials(
    todd_rows: list[dict[str, Any]],
    *,
    attributes: list[dict[str, Any]],
    dancers: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (officials, edition_officials).

    Confident dancer link: unique normalized full name match against dancers.
    Only emit officials for editions present in ``attributes`` (occurred/matched).
    """
    attr_keys = {
        (a["event_id"], a["event_year"], a["event_month"]): a for a in attributes
    }
    attr_by_todd = {a["todd_edition_id"]: a for a in attributes}

    name_to_dancers: dict[str, list[int]] = {}
    for d in dancers:
        first = (d.get("first_name") or "").strip()
        last = (d.get("last_name") or "").strip()
        full = normalize_person_name(f"{first} {last}")
        if not full:
            continue
        name_to_dancers.setdefault(full, []).append(int(d["dancer_id"]))

    people: dict[str, dict[str, Any]] = {}
    bridges: list[dict[str, Any]] = []

    def ensure_person(display: str) -> int | None:
        key = normalize_person_name(display)
        if not key:
            return None
        if key not in people:
            ids = name_to_dancers.get(key) or []
            dancer_id = ids[0] if len(ids) == 1 else None
            people[key] = {
                "official_id": len(people) + 1,
                "canonical_name": display.strip(),
                "name_normalized": key,
                "dancer_id": dancer_id,
            }
        return int(people[key]["official_id"])

    for row in todd_rows:
        attr = attr_by_todd.get(row["todd_edition_id"])
        if attr is None:
            continue
        eid, y, m = attr["event_id"], attr["event_year"], attr["event_month"]
        if (eid, y, m) not in attr_keys:
            continue

        for role, field in (("chief_judge", "chief_judge"), ("scoreperson", "scoreperson")):
            name = row.get(field)
            if not name:
                continue
            oid = ensure_person(name)
            if oid is None:
                continue
            bridges.append(
                {
                    "event_id": eid,
                    "event_year": y,
                    "event_month": m,
                    "official_id": oid,
                    "role": role,
                    "rounds": None,
                    "panel_order": None,
                }
            )

        judges = _as_list(row.get("judges"))
        rounds = _as_list(row.get("judge_rounds"))
        for i, name in enumerate(judges):
            oid = ensure_person(name)
            if oid is None:
                continue
            r = rounds[i] if i < len(rounds) else None
            bridges.append(
                {
                    "event_id": eid,
                    "event_year": y,
                    "event_month": m,
                    "official_id": oid,
                    "role": "judge",
                    "rounds": r or None,
                    "panel_order": i + 1,
                }
            )

    officials = sorted(people.values(), key=lambda r: r["official_id"])
    return officials, bridges

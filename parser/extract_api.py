"""Extract CSV rows from WSDC lookup2020/find JSON (notebook-compatible)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from transform.normalize import normalize_dancer_name

UPDATE_DATE = date.today().isoformat()


def extract_role_row(dancer_data: dict[str, Any]) -> dict[str, Any]:
    dancer_first = dancer_data.get("dancer_first", "").replace("\t", "").strip()
    dancer_last = dancer_data.get("dancer_last", "").replace("\t", "").strip()
    non_dom_lookup = dancer_data.get("non_dominate_lookup") or []
    if non_dom_lookup and isinstance(non_dom_lookup, list):
        non_dom = non_dom_lookup[0]
        non_dominate_required = non_dom.get("non_dominate_required", "")
        non_dominate_allowed = non_dom.get("non_dominate_allowed", "")
        non_dominate_recommended = non_dom.get("non_dominate_recommended", "")
    else:
        non_dominate_required = non_dominate_allowed = non_dominate_recommended = ""

    return {
        "dancer_id": dancer_data.get("dancer_wsdcid", ""),
        "dancer_name": normalize_dancer_name(f"{dancer_first} {dancer_last}") or "",
        "dominate_role": dancer_data.get("short_dominate_role", ""),
        "dominate_required": dancer_data.get("dominate_required", ""),
        "dominate_allowed": dancer_data.get("dominate_allowed", ""),
        "non_dominate_role": dancer_data.get("short_non_dominate_role", ""),
        "non_dominate_required": non_dominate_required,
        "non_dominate_allowed": non_dominate_allowed,
        "non_dominate_recommended": non_dominate_recommended,
        "non_dominate_role_highest_level_points": dancer_data.get(
            "non_dominate_role_highest_level_points", ""
        ),
        "non_dominate_role_highest_level": dancer_data.get(
            "non_dominate_role_highest_level", ""
        ),
        "update_date": UPDATE_DATE,
    }


def extract_points_rows(dancer_data: dict[str, Any]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    dancer_id = dancer_data.get("dancer_wsdcid", "")
    for role in ("leader", "follower"):
        role_data = dancer_data.get(role)
        if not isinstance(role_data, dict):
            continue
        placements = role_data.get("placements") or {}
        if not isinstance(placements, dict):
            continue
        for dance, dance_data in placements.items():
            if not isinstance(dance_data, dict):
                continue
            for level, level_data in dance_data.items():
                if isinstance(level_data, dict):
                    rows.append([
                        dancer_id,
                        role,
                        dance,
                        level,
                        level_data.get("total_points"),
                        UPDATE_DATE,
                    ])
    return rows


def extract_results_rows(dancer_data: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    dancer_id = dancer_data.get("dancer_wsdcid", "")
    for event_role, role_data in dancer_data.items():
        if event_role not in ("leader", "follower") or not isinstance(role_data, dict):
            continue
        placements = role_data.get("placements") or {}
        if not isinstance(placements, dict):
            continue
        for dance, dance_data in placements.items():
            if not isinstance(dance_data, dict):
                continue
            for level, level_data in dance_data.items():
                if not isinstance(level_data, dict):
                    continue
                division = level_data.get("division") or {}
                event_competition = division.get("name", "") if isinstance(division, dict) else ""
                competitions = level_data.get("competitions") or []
                if not isinstance(competitions, list):
                    continue
                for competition in competitions:
                    if not isinstance(competition, dict):
                        continue
                    event = competition.get("event") or {}
                    if not isinstance(event, dict):
                        continue
                    rows.append({
                        "dancer_id": dancer_id,
                        "event_dance": dance,
                        "event_competition": event_competition,
                        "event_role": event_role,
                        # event.id is the stable WSDC event id (event_name_id);
                        # event.location is the raw place string used to resolve
                        # location_id against location_info. The API does NOT
                        # return a numeric location_id, so both are captured here
                        # and location_id is filled later in preprocess.
                        "event_name_id": event.get("id", ""),
                        "event_name": event.get("name", ""),
                        "event_location": event.get("location", ""),
                        "event_result": competition.get("result", ""),
                        "event_points": competition.get("points", ""),
                        "location_id": event.get("location_id", ""),
                        "event_year": event.get("year", ""),
                        "event_month": event.get("month", ""),
                        "event_year_and_month": event.get("date", ""),
                    })
    return rows


def extract_event_names(dancer_data: dict[str, Any]) -> list[str]:
    """Unique WSDC event names from a lookup2020/find payload."""
    names: set[str] = set()
    for row in extract_results_rows(dancer_data):
        name = (row.get("event_name") or "").strip()
        if name:
            names.add(name)
    return sorted(names)


def build_frames(records: list[dict[str, Any]]) -> dict[str, pd.DataFrame]:
    role_rows = [extract_role_row(r) for r in records]
    points_rows: list[list[Any]] = []
    results_rows: list[dict[str, Any]] = []
    for record in records:
        points_rows.extend(extract_points_rows(record))
        results_rows.extend(extract_results_rows(record))

    return {
        "dancer_role_info.csv": pd.DataFrame(role_rows),
        "dancers_points_info.csv": pd.DataFrame(
            points_rows,
            columns=["dancer_id", "role", "dance", "level", "total_points", "update_date"],
        ),
        "dancers_results_info.csv": pd.DataFrame(results_rows),
    }

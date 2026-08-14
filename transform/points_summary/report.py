"""Build Point Summary event reports from pipeline CSV exports.

Port of the Telegram bot's results_report_utils + overrides, adapted to take
explicit CSV paths and normalized edition metadata from event_editions.
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from transform.knowledge.geo_flags import resolve_flag_and_continent
from transform.points_summary.advancement import (
    ensure_event_points_timeline,
    get_advancement_status,
)

PLACE_EMOJI = {"1": "🥇", "2": "🥈", "3": "🥉"}

DIVISION_ORDER = [
    "Champions",
    "All-Stars",
    "Advanced",
    "Sophisticated",
    "Intermediate",
    "Novices",
    "Newcomers",
    "Masters",
    "Juniors",
]

# Canonical display names for known spelling variants in results CSV.
DIVISION_CANONICAL = {
    "champion": "Champions",
    "champions": "Champions",
    "all-star": "All-Stars",
    "all-stars": "All-Stars",
    "allstar": "All-Stars",
    "allstars": "All-Stars",
    "advanced": "Advanced",
    "sophisticated": "Sophisticated",
    "intermediate": "Intermediate",
    "novice": "Novices",
    "novices": "Novices",
    "newcomer": "Newcomers",
    "newcomers": "Newcomers",
    "masters": "Masters",
    "master": "Masters",
    "juniors": "Juniors",
    "junior": "Juniors",
}

MANUAL_RESULT_ID_OVERRIDES = {
    ("easter swing 2026", "all-stars", "1", "leader", "2691"): "20691",
    ("swing over", "champions", "5", "follower", "16091"): "14091",
}

MANUAL_TOTAL_DELTA_OVERRIDES = {
    ("easter swing 2026", "all-stars", "1", "leader", "20691"): 10,
    ("swing over", "champions", "5", "follower", "14091"): 1,
}

MANUAL_MISSING_ROLE_PLACE_OVERRIDES = {
    ("detonation dance", "all-stars", "3", "leader"): "1",
}


def canonicalize_division(name: str) -> str:
    key = (name or "").strip().lower()
    return DIVISION_CANONICAL.get(key, (name or "").strip())


def _normalize_division_key(name: str) -> str:
    canon = canonicalize_division(name)
    norm = canon.strip().lower()
    if norm in {"all-star", "allstars", "all-stars"}:
        return "all-stars"
    return norm


def make_event_slug(event_name: str, start_date: str) -> str:
    """Stable edition slug: YYYY-MM-DD-event-name (start_date based)."""
    date_part = (start_date or "").strip()[:10]
    slug = re.sub(r"[^a-z0-9]+", "-", (event_name or "").lower()).strip("-")
    return f"{date_part}-{slug}" if slug else date_part


def format_date_range(start: date | None, end: date | None) -> str:
    if not start or not end:
        return ""
    if start.year == end.year:
        if start.month == end.month:
            return f"{start.strftime('%b %d')} - {end.strftime('%d, %Y')}"
        return f"{start.strftime('%b %d')} - {end.strftime('%b %d, %Y')}"
    return f"{start.strftime('%b %d, %Y')} - {end.strftime('%b %d, %Y')}"


def _parse_iso_date(value: Any) -> date | None:
    if value is None or (isinstance(value, float) and str(value) == "nan"):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def load_dancers_map(dancers_csv: Path) -> Dict[str, str]:
    dancers: Dict[str, str] = {}
    with Path(dancers_csv).open("r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            did = (row.get("dancer_id") or "").strip()
            name = (row.get("dancer_name") or "").strip()
            if did:
                dancers[did] = name or "???"
    return dancers


def load_results_rows(results_csv: Path) -> List[dict]:
    with Path(results_csv).open("r", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _apply_manual_result_override(
    event_name: str,
    division: str,
    place: str,
    role: str,
    dancer_id: str,
) -> str:
    key = (
        (event_name or "").strip().lower(),
        _normalize_division_key(division),
        (place or "").strip(),
        (role or "").strip().lower(),
        (dancer_id or "").strip(),
    )
    return MANUAL_RESULT_ID_OVERRIDES.get(key, dancer_id)


def _apply_manual_total_delta_override(
    event_name: str,
    division: str,
    place: str,
    role: str,
    dancer_id: str,
    total_after: str,
) -> str:
    key = (
        (event_name or "").strip().lower(),
        _normalize_division_key(division),
        (place or "").strip(),
        (role or "").strip().lower(),
        (dancer_id or "").strip(),
    )
    delta = MANUAL_TOTAL_DELTA_OVERRIDES.get(key, 0)
    if not delta:
        return total_after
    try:
        return str(int(total_after) + int(delta))
    except (TypeError, ValueError):
        return total_after


def _manual_missing_role_source_place(
    event_name: str,
    division: str,
    place: str,
    missing_role: str,
) -> Optional[str]:
    key = (
        (event_name or "").strip().lower(),
        _normalize_division_key(division),
        (place or "").strip(),
        (missing_role or "").strip().lower(),
    )
    return MANUAL_MISSING_ROLE_PLACE_OVERRIDES.get(key)


def _copy_role_from_place(
    division_results: dict,
    source_place: str,
    role: str,
) -> List[dict]:
    bucket = division_results.get(source_place, {})
    key = "leaders" if role == "leader" else "followers"
    items = bucket.get(key, [])
    if not items:
        return []
    src = items[0]
    return [{"id": src["id"], "points": "0"}]


def resolve_podium_roles(
    event_name: str,
    division: str,
    place: str,
    leaders: List[dict],
    followers: List[dict],
    division_results: dict,
) -> Tuple[List[dict], List[dict]]:
    leaders = list(leaders)
    followers = list(followers)
    if not place.isdigit() or int(place) > 3:
        return leaders, followers

    if not leaders:
        src_place = _manual_missing_role_source_place(
            event_name, division, place, "leader"
        )
        if not src_place and place == "2" and division_results.get("1", {}).get("leaders"):
            src_place = "1"
        if (
            src_place
            and src_place in division_results
            and division_results[src_place].get("leaders")
        ):
            leaders = _copy_role_from_place(division_results, src_place, "leader")

    if not followers:
        src_place = _manual_missing_role_source_place(
            event_name, division, place, "follower"
        )
        if (
            not src_place
            and place == "2"
            and division_results.get("1", {}).get("followers")
        ):
            src_place = "1"
        if (
            src_place
            and src_place in division_results
            and division_results[src_place].get("followers")
        ):
            followers = _copy_role_from_place(division_results, src_place, "follower")

    return leaders, followers


def _event_name_matches(row_name: str, target: str) -> bool:
    a = re.sub(r"\s+", " ", (row_name or "").strip().lower())
    b = re.sub(r"\s+", " ", (target or "").strip().lower())
    return a == b


def collect_event_results(
    event_name: str,
    results_rows: Iterable[dict],
    *,
    event_year: str | int | None = None,
    event_month: str | int | None = None,
) -> dict:
    """All places for one event, keyed by canonical division → place → roles."""
    results: dict = defaultdict(lambda: defaultdict(lambda: {"leaders": [], "followers": []}))
    year_s = str(event_year).strip() if event_year is not None else None
    month_s = str(int(event_month)) if event_month not in (None, "") else None

    for row in results_rows:
        if not _event_name_matches(row.get("event_name", ""), event_name):
            continue
        if year_s and str(row.get("event_year", "")).strip() != year_s:
            continue
        if month_s:
            try:
                row_month = str(int(str(row.get("event_month", "")).strip()))
            except ValueError:
                continue
            if row_month != month_s:
                continue

        division = canonicalize_division(row.get("event_competition", ""))
        if not division:
            continue
        place = (row.get("event_result") or "").strip()
        role = (row.get("event_role") or "").strip().lower()
        dancer_id = _apply_manual_result_override(
            row.get("event_name", ""),
            row.get("event_competition", ""),
            place,
            role,
            row.get("dancer_id", ""),
        )
        points = (row.get("event_points") or "").strip()
        if role == "leader":
            results[division][place]["leaders"].append({"id": dancer_id, "points": points})
        elif role == "follower":
            results[division][place]["followers"].append({"id": dancer_id, "points": points})

    return {div: dict(places) for div, places in results.items()}


def event_has_top3(all_results: dict) -> bool:
    for places in all_results.values():
        for place in ("1", "2", "3"):
            bucket = places.get(place) or {}
            if bucket.get("leaders") or bucket.get("followers"):
                return True
    return False


def _format_dancer_result_line(
    dancer_id: str,
    points: str,
    role: str,
    division: str,
    is_newcomer: bool,
    event_name: str,
    place: str,
    dancers_map: Dict[str, str],
    points_csv: Path,
    as_of: date | None = None,
) -> str:
    name = dancers_map.get(dancer_id, "???")
    if is_newcomer:
        return f"{name} (+{points})"
    _, total_after, status = get_advancement_status(
        dancer_id, role, division, points, points_csv, as_of=as_of
    )
    total_after = _apply_manual_total_delta_override(
        event_name, division, place, role, dancer_id, str(total_after)
    )
    line = f"{name} (+{points}) [{total_after}]"
    if status:
        line += f" {status}"
    return line


def _pair_or_list_place(
    *,
    event_name: str,
    division: str,
    place: str,
    place_label: str,
    leaders: List[dict],
    followers: List[dict],
    is_newcomer: bool,
    dancers_map: Dict[str, str],
    points_csv: Path,
    include_points_on_single: bool = True,
    as_of: date | None = None,
) -> dict | None:
    if leaders and followers:
        ld, fd = leaders[0], followers[0]
        if is_newcomer:
            leader_s = f"{dancers_map.get(ld['id'], '???')} (+{ld['points']})"
            follower_s = f"{dancers_map.get(fd['id'], '???')} (+{fd['points']})"
        else:
            _, la, ls = get_advancement_status(
                ld["id"], "leader", division, ld["points"], points_csv, as_of=as_of
            )
            _, fa, fs = get_advancement_status(
                fd["id"], "follower", division, fd["points"], points_csv, as_of=as_of
            )
            la = _apply_manual_total_delta_override(
                event_name, division, place, "leader", ld["id"], str(la)
            )
            fa = _apply_manual_total_delta_override(
                event_name, division, place, "follower", fd["id"], str(fa)
            )
            leader_s = f"{dancers_map.get(ld['id'], '???')} (+{ld['points']}) [{la}]"
            if ls:
                leader_s += f" {ls}"
            follower_s = f"{dancers_map.get(fd['id'], '???')} (+{fd['points']}) [{fa}]"
            if fs:
                follower_s += f" {fs}"
        return {
            "place": place,
            "place_label": place_label,
            "leader": leader_s,
            "follower": follower_s,
        }

    if leaders:
        items = [
            _format_dancer_result_line(
                ld["id"],
                ld["points"],
                "leader",
                division,
                is_newcomer,
                event_name,
                place,
                dancers_map,
                points_csv,
                as_of,
            )
            if include_points_on_single
            else dancers_map.get(ld["id"], "???")
            for ld in leaders
        ]
        return {
            "place": place,
            "place_label": place_label,
            "leader": None,
            "follower": None,
            "leaders": items,
        }

    if followers:
        items = [
            _format_dancer_result_line(
                fd["id"],
                fd["points"],
                "follower",
                division,
                is_newcomer,
                event_name,
                place,
                dancers_map,
                points_csv,
                as_of,
            )
            if include_points_on_single
            else dancers_map.get(fd["id"], "???")
            for fd in followers
        ]
        return {
            "place": place,
            "place_label": place_label,
            "leader": None,
            "follower": None,
            "followers": items,
        }
    return None


def build_full_event_report(
    event_meta: dict,
    results_rows: List[dict],
    dancers_map: Dict[str, str],
    points_csv: Path,
) -> Optional[dict]:
    """Full JSON report for one edition (all divisions / places)."""
    event_name = event_meta["name"]
    all_results = collect_event_results(
        event_name,
        results_rows,
        event_year=event_meta.get("event_year"),
        event_month=event_meta.get("event_month"),
    )
    if not all_results or not event_has_top3(all_results):
        return None

    as_of = _parse_iso_date(event_meta.get("start_date"))
    if as_of is None:
        try:
            as_of = date(
                int(event_meta.get("event_year")),
                int(event_meta.get("event_month")),
                1,
            )
        except (TypeError, ValueError):
            as_of = None
    ensure_event_points_timeline(results_rows)

    divisions_out: List[dict] = []
    ordered = [d for d in DIVISION_ORDER if d in all_results]
    ordered.extend(sorted(d for d in all_results if d not in DIVISION_ORDER))

    for division in ordered:
        results = all_results[division]
        places_out: List[dict] = []
        places_sorted = sorted(
            results.keys(),
            key=lambda x: 999 if x == "F" else (int(x) if str(x).isdigit() else 999),
        )
        is_newcomer = division in {"Newcomer", "Newcomers"}

        for place in places_sorted:
            data = results[place]
            leaders = list(data.get("leaders", []))
            followers = list(data.get("followers", []))
            place_emoji = PLACE_EMOJI.get(place, "")

            if str(place).isdigit():
                place_int = int(place)
                place_label = (
                    f"{place_emoji} {place} place".strip()
                    if place_emoji
                    else f"{place} place"
                )
                if place_int <= 3:
                    leaders, followers = resolve_podium_roles(
                        event_name, division, place, leaders, followers, results
                    )
                if place_int <= 5:
                    rec = _pair_or_list_place(
                        event_name=event_name,
                        division=division,
                        place=place,
                        place_label=place_label,
                        leaders=leaders,
                        followers=followers,
                        is_newcomer=is_newcomer,
                        dancers_map=dancers_map,
                        points_csv=points_csv,
                        as_of=as_of,
                    )
                    if rec:
                        places_out.append(rec)
            elif place == "F" and (leaders or followers):
                lp = leaders[0]["points"] if leaders else None
                fp = followers[0]["points"] if followers else None
                leader_items = []
                for ld in leaders:
                    ln = dancers_map.get(ld["id"], "???")
                    if is_newcomer:
                        leader_items.append(ln)
                    else:
                        _, la, ls = get_advancement_status(
                            ld["id"],
                            "leader",
                            division,
                            ld["points"],
                            points_csv,
                            as_of=as_of,
                        )
                        item = f"{ln} [{la}]"
                        if ls:
                            item += f" {ls}"
                        leader_items.append(item)
                follower_items = []
                for fd in followers:
                    fn = dancers_map.get(fd["id"], "???")
                    if is_newcomer:
                        follower_items.append(fn)
                    else:
                        _, fa, fs = get_advancement_status(
                            fd["id"],
                            "follower",
                            division,
                            fd["points"],
                            points_csv,
                            as_of=as_of,
                        )
                        item = f"{fn} [{fa}]"
                        if fs:
                            item += f" {fs}"
                        follower_items.append(item)
                rec: dict = {
                    "place": "F",
                    "place_label": "Final",
                    "leader": None,
                    "follower": None,
                }
                if leader_items:
                    rec["leaders"] = leader_items
                    if lp is not None:
                        rec["points_leader"] = lp
                if follower_items:
                    rec["followers"] = follower_items
                    if fp is not None:
                        rec["points_follower"] = fp
                places_out.append(rec)

        if places_out:
            divisions_out.append({"division": division, "places": places_out})

    if not divisions_out:
        return None

    flag, continent = resolve_flag_and_continent(
        country=event_meta.get("country"),
        location=event_meta.get("location"),
    )
    return {
        "name": event_name,
        "location": event_meta.get("location") or "",
        "dates": event_meta.get("dates") or "",
        "flag": event_meta.get("flag") or flag,
        "continent": event_meta.get("continent") or continent,
        "telegraph_url": event_meta.get("telegraph_url"),
        "divisions": divisions_out,
        "start_date": event_meta.get("start_date"),
        "end_date": event_meta.get("end_date"),
    }


def edition_meta_from_row(row: dict) -> dict:
    start = _parse_iso_date(row.get("start_date"))
    end = _parse_iso_date(row.get("end_date"))
    location = (
        (row.get("location_raw") or "").strip()
        or ", ".join(
            p
            for p in [
                (row.get("place_city") or "").strip(),
                (row.get("place_state") or "").strip(),
                (row.get("place_country") or "").strip(),
            ]
            if p
        )
    )
    country = (row.get("place_country") or "").strip() or None
    flag, continent = resolve_flag_and_continent(country=country, location=location)
    return {
        "name": (row.get("event_name") or "").strip(),
        "event_id": row.get("event_id"),
        "edition_id": row.get("edition_id"),
        "event_year": row.get("event_year"),
        "event_month": row.get("event_month"),
        "start_date": start.isoformat() if start else None,
        "end_date": end.isoformat() if end else None,
        "dates": format_date_range(start, end),
        "location": location,
        "country": country,
        "flag": flag,
        "continent": continent,
    }

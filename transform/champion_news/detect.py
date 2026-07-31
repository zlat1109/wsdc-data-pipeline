"""Detect Allowed / Required Champion crossings from results timelines."""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from transform.champion_news.thresholds import (
    ALS_ALLOWED,
    ALS_REQUIRED,
    CHMP_REQUIRED,
    PATHWAY_ALS_225,
    PATHWAY_CHMP_10,
    STATUS_ALLOWED,
    STATUS_REQUIRED,
    division_code,
)
from transform.knowledge.geo_flags import continent_for_country, flag_for_country


@dataclass(frozen=True)
class ResultEvent:
    dancer_id: str
    role: str
    event_name: str
    event_year: int
    event_month: int
    event_points: float
    division: str  # ALS / CHMP / ...
    location_id: str
    start_date: date | None
    end_date: date | None
    place_city: str
    place_country: str
    location_display: str


def _parse_int(value: object, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _parse_float(value: object) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def _parse_iso(value: object) -> date | None:
    text = str(value or "").strip()[:10]
    if not text or text.lower() in {"nan", "none"}:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def load_edition_dates(path: Path) -> dict[tuple[str, int, int], tuple[date | None, date | None, str, str, str]]:
    """(event_name_norm, year, month) → (start, end, city, country, location_display)."""
    out: dict[tuple[str, int, int], tuple[date | None, date | None, str, str, str]] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            name = " ".join((row.get("event_name") or "").strip().lower().split())
            year = _parse_int(row.get("event_year"))
            month = _parse_int(row.get("event_month"))
            if not name or not year or not month:
                continue
            city = (row.get("place_city") or "").strip()
            country = (row.get("place_country") or "").strip()
            raw = (row.get("location_raw") or "").strip()
            display = raw or (", ".join(p for p in (city, country) if p))
            out[(name, year, month)] = (
                _parse_iso(row.get("start_date")),
                _parse_iso(row.get("end_date")),
                city,
                country,
                display,
            )
    return out


def load_location_display(path: Path) -> dict[str, tuple[str, str, str]]:
    """location_id → (city, country, display)."""
    out: dict[str, tuple[str, str, str]] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            lid = (row.get("location_id") or "").strip()
            if not lid:
                continue
            city = (row.get("event_city") or "").strip()
            country = (row.get("event_country") or "").strip()
            display = (
                (row.get("event_location_standardized") or "").strip()
                or (row.get("event_location") or "").strip()
                or ", ".join(p for p in (city, country) if p)
            )
            out[lid] = (city, country, display)
    return out


def load_dancer_names(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            did = (row.get("dancer_id") or "").strip()
            name = (row.get("dancer_name") or "").strip()
            if did and name:
                out[did] = name
    return out


def load_timeline_events(data_dir: Path) -> dict[tuple[str, str], list[ResultEvent]]:
    """Group point-bearing WCS results by (dancer_id, role)."""
    editions = load_edition_dates(data_dir / "event_editions.csv")
    locations = load_location_display(data_dir / "location_info.csv")
    results_path = data_dir / "dancers_results_info.csv"
    grouped: dict[tuple[str, str], list[ResultEvent]] = defaultdict(list)
    if not results_path.exists():
        return grouped

    with results_path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if (row.get("event_dance") or "").strip() != "West Coast Swing":
                continue
            points = _parse_float(row.get("event_points"))
            if points <= 0:
                continue
            dancer_id = (row.get("dancer_id") or "").strip()
            role = (row.get("event_role") or "").strip().lower()
            if not dancer_id or role not in {"leader", "follower"}:
                continue
            year = _parse_int(row.get("event_year"))
            month = _parse_int(row.get("event_month"))
            if not year or not month:
                continue
            name = (row.get("event_name") or "").strip()
            div = division_code(row.get("event_competition") or "")
            lid = (row.get("location_id") or "").strip()
            key_name = " ".join(name.lower().split())
            start, end, city, country, display = editions.get(
                (key_name, year, month), (None, None, "", "", "")
            )
            if lid and lid in locations:
                city, country, display = locations[lid]
            elif not display and lid:
                display = lid
            grouped[(dancer_id, role)].append(
                ResultEvent(
                    dancer_id=dancer_id,
                    role=role,
                    event_name=name,
                    event_year=year,
                    event_month=month,
                    event_points=points,
                    division=div,
                    location_id=lid,
                    start_date=start,
                    end_date=end,
                    place_city=city,
                    place_country=country,
                    location_display=display,
                )
            )
    return grouped


def _sort_key(ev: ResultEvent) -> tuple:
    # Prefer day-level start_date; fall back to year-month then name.
    day = ev.start_date or date(ev.event_year, ev.event_month, 1)
    return (day, ev.event_name.lower())


def _accumulate_crossing(
    events: list[ResultEvent],
) -> tuple[dict | None, dict | None]:
    """Return (allowed_crossing, required_crossing) dict payloads or None."""
    ordered = sorted(events, key=_sort_key)
    als = 0.0
    chmp = 0.0
    allowed: dict | None = None
    required: dict | None = None

    # Aggregate points per (name, year, month) before walking so duplicate rows
    # in the same edition do not invent false mid-edition crossings.
    edition_buckets: dict[tuple[str, int, int], list[ResultEvent]] = defaultdict(list)
    for ev in ordered:
        edition_buckets[(ev.event_name, ev.event_year, ev.event_month)].append(ev)

    walk_order = sorted(
        edition_buckets.keys(),
        key=lambda k: _sort_key(edition_buckets[k][0]),
    )

    for key in walk_order:
        bucket = edition_buckets[key]
        als_add = sum(e.event_points for e in bucket if e.division == "ALS")
        chmp_add = sum(e.event_points for e in bucket if e.division == "CHMP")
        prev_als, prev_chmp = als, chmp
        als += als_add
        chmp += chmp_add
        # Representative event: prefer one that contributed ALS/CHMP points.
        rep = next((e for e in bucket if e.division in {"ALS", "CHMP"}), bucket[0])
        threshold_date = rep.start_date or date(rep.event_year, rep.event_month, 1)

        if allowed is None and prev_als < ALS_ALLOWED <= als:
            allowed = _crossing_payload(
                status=STATUS_ALLOWED,
                pathway=None,
                event=rep,
                threshold_date=threshold_date,
                als_total=als,
                chmp_total=chmp,
            )

        if required is None:
            pathway = None
            if prev_als < ALS_REQUIRED <= als:
                pathway = PATHWAY_ALS_225
            elif prev_chmp < CHMP_REQUIRED <= chmp:
                pathway = PATHWAY_CHMP_10
            if pathway:
                required = _crossing_payload(
                    status=STATUS_REQUIRED,
                    pathway=pathway,
                    event=rep,
                    threshold_date=threshold_date,
                    als_total=als,
                    chmp_total=chmp,
                )

        if allowed is not None and required is not None:
            break

    return allowed, required


def _crossing_payload(
    *,
    status: str,
    pathway: str | None,
    event: ResultEvent,
    threshold_date: date,
    als_total: float,
    chmp_total: float,
) -> dict:
    country = event.place_country
    return {
        "status": status,
        "required_pathway": pathway,
        "dancer_id": event.dancer_id,
        "role": event.role,
        "threshold_date": threshold_date.isoformat(),
        "threshold_event": event.event_name,
        "threshold_location": event.location_display,
        "threshold_city": event.place_city,
        "threshold_country": country,
        "continent": continent_for_country(country) if country else "",
        "flag": flag_for_country(country) if country else "",
        "als_total": int(als_total),
        "chmp_total": int(chmp_total),
        "event_year": event.event_year,
        "event_month": event.event_month,
    }


def make_transition_slug(
    threshold_date: str,
    dancer_id: str,
    role: str,
    status: str,
) -> str:
    return f"{threshold_date[:10]}-{dancer_id}-{role}-{status}"


def detect_transitions(
    data_dir: Path,
    *,
    cutoff: date,
    timelines: dict[tuple[str, str], list[ResultEvent]] | None = None,
    names: dict[str, str] | None = None,
) -> list[dict]:
    """Return candidate transition cards with threshold_date >= cutoff."""
    if names is None:
        names = load_dancer_names(data_dir / "dancer_role_info.csv")
    if timelines is None:
        timelines = load_timeline_events(data_dir)
    candidates: list[dict] = []

    for (dancer_id, role), events in timelines.items():
        allowed, required = _accumulate_crossing(events)
        for crossing in (allowed, required):
            if not crossing:
                continue
            tdate = date.fromisoformat(crossing["threshold_date"])
            if tdate < cutoff:
                continue
            slug = make_transition_slug(
                crossing["threshold_date"],
                dancer_id,
                role,
                crossing["status"],
            )
            card = {
                **crossing,
                "slug": slug,
                "dancer_name": names.get(dancer_id, dancer_id),
                "title": _headline(names.get(dancer_id, dancer_id), crossing),
            }
            candidates.append(card)
    return candidates


def _headline(name: str, crossing: dict) -> str:
    status = crossing["status"]
    role = crossing["role"]
    if status == STATUS_ALLOWED:
        label = "Allowed to Champions"
    else:
        pathway = crossing.get("required_pathway")
        if pathway == PATHWAY_CHMP_10:
            label = "Required to Champions (via Champions points)"
        else:
            label = "Required to Champions"
    return f"{name} — {label} ({role})"


def iter_events_for_dancer_role(
    timelines: dict[tuple[str, str], list[ResultEvent]],
    dancer_id: str,
    role: str,
) -> Iterable[ResultEvent]:
    return timelines.get((dancer_id, role), [])

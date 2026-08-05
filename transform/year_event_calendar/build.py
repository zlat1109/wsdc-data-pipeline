"""Build events_year_calendar.json payload from pipeline CSVs."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from transform.knowledge.calendar_operator_overrides import (
    CALENDAR_OPERATOR_OVERRIDES,
)
from transform.knowledge.event_aliases import (
    EVENT_NAME_VARIANT_TO_CATALOG,
    EVENT_NAME_YEAR_SPLITS,
    MERGE_EVENT_ID_MAP,
    RESULT_TO_CATALOG_EVENT_NAME,
)
from transform.knowledge.geo_flags import continent_for_country
from transform.year_event_calendar.expected import (
    EXPECTED_STALE_GRACE_DAYS,
    EXPECTED_WINDOW_DAYS,
    is_stale_expected,
    iter_expected_candidates,
    match_expected_to_confirmed,
    project_start_to_year,
)
from transform.year_event_calendar.weekends import weekend_bounds, weekend_key

STATUS_CONFIRMED = "confirmed"
STATUS_EXPECTED = "expected"
STATUS_CANCELLED = "cancelled"
STATUS_HIATUS = "hiatus"

KIND_REGISTRY = "registry"
KIND_TRIAL = "trial"

# From 2025 WSDC awards registry points at trial events, so a series' first
# points year is a usable (heuristic) trial signal for that calendar year only.
TRIAL_FIRST_YEAR_HEURISTIC_FROM = 2025

# Public calendar uses four continents (South America folds into America).
CALENDAR_CONTINENTS = ("America", "Europe", "Asia", "Australia")

# Optional series successor links for expected suppression when two live registry
# ids must stay split. Prefer MERGE_EVENT_ID_MAP + EVENT_NAME_YEAR_SPLITS (one id,
# year-aware display) for rebrands / WSDC id reuse.
SERIES_SUCCESSOR_MAP: dict[int, int] = {}

_NAME_ALIAS_LOOKUP = {
    **{k.lower(): v for k, v in RESULT_TO_CATALOG_EVENT_NAME.items()},
    **{k.lower(): v for k, v in EVENT_NAME_VARIANT_TO_CATALOG.items()},
}

_NAME_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "of",
        "for",
        "wcs",
        "west",
        "coast",
        "swing",
        "dance",
        "championships",
        "championship",
        "open",
        "classic",
        "festival",
        "ball",
        "party",
        "fest",
        "weekend",
        "invitational",
        "nationals",
        "national",
        "convention",
    }
)


def _parse_date(value: Any) -> date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _clean_name(value: Any) -> str | None:
    """Return a display name, or None if missing / pandas NaN stringified."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "nat", "unknown event"}:
        return None
    return text


def _truthy(value: Any) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "t", "true", "yes", "y"}


def _norm_status_calendar(raw: Any) -> str | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    text = str(raw).strip().lower()
    if text in {"cancelled", "canceled"}:
        return STATUS_CANCELLED
    if text in {"hiatus", "on_hiatus"}:
        return STATUS_HIATUS
    if text in {"unconfirmed", "unconirmed"}:
        return STATUS_EXPECTED
    if text in {"scheduled", "confirmed"}:
        return STATUS_CONFIRMED
    return None


def _kind_from_status_event(raw: Any, name: str = "") -> str:
    text = f"{raw or ''} {name or ''}".lower()
    if "trial" in text:
        return KIND_TRIAL
    return KIND_REGISTRY


def _status_flags_say_trial(*values: Any) -> bool:
    for value in values:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            continue
        if "trial" in str(value).strip().lower():
            return True
    return False


def _first_points_year_by_event(data_dir: Path, catalog: pd.DataFrame) -> dict[int, int]:
    """Earliest year an event appears with points/results (catalog + editions)."""
    out: dict[int, int] = {}
    if not catalog.empty and "first_edition_year" in catalog.columns:
        for rec in catalog.to_dict(orient="records"):
            eid = rec.get("event_id")
            year = rec.get("first_edition_year")
            if eid is None or (isinstance(eid, float) and pd.isna(eid)):
                continue
            if year is None or (isinstance(year, float) and pd.isna(year)):
                continue
            try:
                out[int(eid)] = int(year)
            except (TypeError, ValueError):
                continue

    path = data_dir / "event_editions.csv"
    if path.exists():
        df = pd.read_csv(path, low_memory=False)
        if not df.empty and "event_id" in df.columns:
            df = df.dropna(subset=["event_id"]).copy()
            df["event_id"] = pd.to_numeric(df["event_id"], errors="coerce")
            df["event_year"] = pd.to_numeric(df.get("event_year"), errors="coerce")
            if "result_rows" in df.columns:
                df["result_rows"] = pd.to_numeric(df["result_rows"], errors="coerce").fillna(0)
                scored = df[df["result_rows"] > 0]
            else:
                scored = df
            scored = scored.dropna(subset=["event_id", "event_year"])
            for eid, year in (
                scored.groupby("event_id")["event_year"].min().astype(int).items()
            ):
                eid_i = int(eid)
                prev = out.get(eid_i)
                out[eid_i] = year if prev is None else min(prev, year)
    return out


def _apply_kind_rules(
    rows: list[dict],
    *,
    first_points_year: dict[int, int],
    catalog: pd.DataFrame,
) -> None:
    """Resolve Registry vs Trial with first-year semantics.

    - Expected YoY projections are never Trial (trial is a first-year phase).
    - Live WSDC schedule Trial flags are trusted as published.
    - After a series' first points year, Trial labels (name/catalog) do not stick.
    - From 2025+, first points year ≈ Trial for that year only (rule change heuristic).
    """
    cat_trial_ids: set[int] = set()
    if not catalog.empty and "registry_status" in catalog.columns:
        for rec in catalog.to_dict(orient="records"):
            eid = rec.get("event_id")
            if eid is None or (isinstance(eid, float) and pd.isna(eid)):
                continue
            if _status_flags_say_trial(rec.get("registry_status")):
                cat_trial_ids.add(int(eid))

    for row in rows:
        start = row.get("start_date")
        if not isinstance(start, date):
            row["kind"] = KIND_REGISTRY
            continue
        year = start.year
        eid = row.get("event_id")
        eid_i = int(eid) if eid is not None else None
        first = first_points_year.get(eid_i) if eid_i is not None else None

        if row.get("source") == "expected_yoy":
            row["kind"] = KIND_REGISTRY
            row.pop("kind_from_schedule", None)
            continue

        if row.get("kind_from_schedule"):
            row["kind"] = KIND_TRIAL
            continue

        # Past the first points year → Registry even if title still says Trial Event
        if first is not None and year > first:
            row["kind"] = KIND_REGISTRY
            continue

        name = row.get("name") or ""
        if _kind_from_status_event("", name) == KIND_TRIAL:
            row["kind"] = KIND_TRIAL
            continue

        if row.get("kind") == KIND_TRIAL:
            continue

        if (
            first is not None
            and first == year
            and year >= TRIAL_FIRST_YEAR_HEURISTIC_FROM
        ):
            row["kind"] = KIND_TRIAL
            continue

        if (
            eid_i in cat_trial_ids
            and (first is None or first == year)
        ):
            row["kind"] = KIND_TRIAL
            continue

        row["kind"] = KIND_REGISTRY


def _year_window(as_of: date, *, radius: int = 2) -> list[int]:
    return list(range(as_of.year - radius, as_of.year + radius + 1))


def _load_locations(data_dir: Path) -> pd.DataFrame:
    path = data_dir / "location_info.csv"
    if not path.exists():
        return pd.DataFrame(
            columns=[
                "location_id",
                "event_city",
                "event_country",
                "latitude",
                "longitude",
                "coordinates_valid",
            ]
        )
    loc = pd.read_csv(path)
    loc["location_id"] = pd.to_numeric(loc["location_id"], errors="coerce")
    return loc


def _load_catalog(data_dir: Path) -> pd.DataFrame:
    path = data_dir / "event_catalog.csv"
    if not path.exists():
        return pd.DataFrame(columns=["event_id", "canonical_name", "url", "registry_status"])
    cat = pd.read_csv(path)
    cat["event_id"] = pd.to_numeric(cat["event_id"], errors="coerce")
    return cat


def _norm_place(value: Any) -> str | None:
    text = _clean_name(value)
    return text.lower() if text else None


def _location_id_by_event(data_dir: Path) -> dict[int, int]:
    """Most recent known ``location_id`` per ``event_id`` from event_editions (DB export).

    Scheduled / calendar-date rows often lack ``location_id``; far-future years
    also drop edition rows before dedupe. Inherit the latest edition location so
    map pins can resolve from ``location_info``.
    """
    path = data_dir / "event_editions.csv"
    if not path.exists():
        return {}
    df = pd.read_csv(path, low_memory=False)
    if df.empty or "event_id" not in df.columns or "location_id" not in df.columns:
        return {}
    df = df.dropna(subset=["event_id", "location_id"]).copy()
    if df.empty:
        return {}
    df["event_id"] = pd.to_numeric(df["event_id"], errors="coerce")
    df["location_id"] = pd.to_numeric(df["location_id"], errors="coerce")
    df = df.dropna(subset=["event_id", "location_id"])
    if df.empty:
        return {}
    df["event_id"] = df["event_id"].astype(int)
    df["location_id"] = df["location_id"].astype(int)
    if "start_date" in df.columns:
        df["_start"] = pd.to_datetime(df["start_date"], errors="coerce")
        df = df.sort_values("_start", na_position="first")
    out: dict[int, int] = {}
    for rec in df.to_dict(orient="records"):
        out[int(rec["event_id"])] = int(rec["location_id"])
    return out


def _coords_by_city_country(locations: pd.DataFrame) -> dict[tuple[str, str], tuple[float, float]]:
    """Fallback lat/lon keyed by normalized (city, country) from location_info."""
    out: dict[tuple[str, str], tuple[float, float]] = {}
    if locations.empty:
        return out
    for rec in locations.to_dict(orient="records"):
        if not _truthy(rec.get("coordinates_valid")):
            continue
        city = _norm_place(rec.get("event_city"))
        country = _norm_place(rec.get("event_country"))
        if not city or not country:
            continue
        try:
            lat = float(rec["latitude"])
            lon = float(rec["longitude"])
        except (TypeError, ValueError, KeyError):
            continue
        out[(city, country)] = (lat, lon)
    return out


def _calendar_listing_matches_event(event_name: Any, calendar_title: Any) -> bool:
    """Reject scrape rows matched to the wrong series (e.g. Soul Flow → GGP via URL)."""
    title = _clean_name(calendar_title)
    ename = _clean_name(event_name)
    if not title or not ename:
        return True
    fp_t = set(_fingerprint_event_name(title).split())
    fp_e = set(_fingerprint_event_name(ename).split())
    if not fp_t or not fp_e:
        return True
    return bool(fp_t & fp_e)


def _rows_from_edition_calendar_dates(data_dir: Path) -> list[dict]:
    path = data_dir / "edition_calendar_dates.csv"
    if not path.exists():
        return []
    df = pd.read_csv(path)
    rows: list[dict] = []
    for rec in df.to_dict(orient="records"):
        if not _calendar_listing_matches_event(
            rec.get("event_name"), rec.get("calendar_title")
        ):
            continue
        start = _parse_date(rec.get("planned_start_date"))
        if start is None:
            continue
        end = _parse_date(rec.get("planned_end_date"))
        status = _norm_status_calendar(rec.get("calendar_status")) or STATUS_CONFIRMED
        eid = rec.get("event_id")
        try:
            eid_i = int(eid) if eid is not None and not pd.isna(eid) else None
        except (TypeError, ValueError):
            eid_i = None
        year_raw = rec.get("event_year")
        try:
            year_i = int(year_raw) if year_raw is not None and not pd.isna(year_raw) else start.year
        except (TypeError, ValueError):
            year_i = start.year
        # Prefer the live listing title when present (relocation / rename nuances)
        name = _clean_name(rec.get("calendar_title")) or _clean_name(rec.get("event_name"))
        rows.append(
            {
                "event_id": eid_i,
                "name": name,
                "start_date": start,
                "end_date": end,
                "status": status,
                "kind": _kind_from_status_event("", name or ""),
                "url": _clean_name(rec.get("url")),
                "city": None,
                "country": None,
                "location_id": None,
                "source": "edition_calendar_dates",
                "year": year_i,
            }
        )
    return rows


def _rows_from_operator_overrides() -> list[dict]:
    """Curated hiatus/expected stubs (provisional ids allowed; no WSDC match yet)."""
    rows: list[dict] = []
    for rec in CALENDAR_OPERATOR_OVERRIDES:
        start = rec.get("planned_start_date")
        if not isinstance(start, date):
            start = _parse_date(start)
        if start is None:
            continue
        end = rec.get("planned_end_date")
        if not isinstance(end, date):
            end = _parse_date(end)
        status = _norm_status_calendar(rec.get("calendar_status")) or STATUS_CONFIRMED
        name = _clean_name(rec.get("calendar_title")) or "Unknown event"
        try:
            eid_i = int(rec["event_id"])
            year_i = int(rec.get("event_year") or start.year)
        except (TypeError, ValueError, KeyError):
            continue
        rows.append(
            {
                "event_id": eid_i,
                "name": name,
                "start_date": start,
                "end_date": end if isinstance(end, date) else None,
                "status": status,
                "kind": KIND_REGISTRY,
                "url": _clean_name(rec.get("url")),
                "city": _clean_name(rec.get("city")),
                "country": _clean_name(rec.get("country")),
                "location_id": None,
                "source": "operator_override",
                "year": year_i,
            }
        )
    return rows


def _rows_from_editions(data_dir: Path) -> list[dict]:
    path = data_dir / "event_editions.csv"
    if not path.exists():
        return []
    df = pd.read_csv(path)
    rows: list[dict] = []
    for rec in df.to_dict(orient="records"):
        start = _parse_date(rec.get("start_date"))
        stats_only = False
        try:
            result_rows = int(float(rec.get("result_rows") or 0))
        except (TypeError, ValueError):
            result_rows = 0
        year_raw = rec.get("event_year")
        try:
            year_i = int(year_raw) if year_raw is not None and not pd.isna(year_raw) else None
        except (TypeError, ValueError):
            year_i = None
        if start is None:
            # Results are source of truth: keep result-backed editions even when
            # calendar/list dates were dropped. Do not paint day cells.
            edition_date = _parse_date(rec.get("edition_date"))
            if edition_date is None or result_rows <= 0:
                continue
            start = edition_date
            stats_only = True
            if year_i is None:
                year_i = edition_date.year
        # Month-only placeholders (YYYY-MM-01 with no real calendar day) — skip
        # when date_source is missing and day is 1 and no calendar_status.
        # Keep rows that have calendar_status or date_source day.
        date_source = str(rec.get("date_source") or "").strip().lower()
        cal_status = _norm_status_calendar(rec.get("calendar_status"))
        if (
            not stats_only
            and start.day == 1
            and not cal_status
            and date_source
            not in {
                "wsdc_calendar",
                "wsdc_events_list",
                "day",
            }
        ):
            # Still allow if explicitly marked scheduled with day source elsewhere;
            # bare month stubs are not calendar-grade.
            if date_source in {"", "nan", "month", "edition"}:
                continue
        end = _parse_date(rec.get("end_date"))
        if cal_status in {STATUS_CANCELLED, STATUS_HIATUS}:
            status = cal_status
        elif _truthy(rec.get("event_occurred")) or cal_status == STATUS_CONFIRMED:
            status = STATUS_CONFIRMED
        elif cal_status:
            status = cal_status
        else:
            status = STATUS_CONFIRMED
        eid = rec.get("event_id")
        try:
            eid_i = int(eid) if eid is not None and not pd.isna(eid) else None
        except (TypeError, ValueError):
            eid_i = None
        loc_id = rec.get("location_id")
        try:
            loc_i = int(loc_id) if loc_id is not None and not pd.isna(loc_id) else None
        except (TypeError, ValueError):
            loc_i = None
        name = _clean_name(rec.get("event_name"))
        if year_i is None:
            year_i = start.year
        rows.append(
            {
                "event_id": eid_i,
                "name": name,
                "start_date": start,
                "end_date": end,
                "status": status,
                "kind": _kind_from_status_event(rec.get("registry_status"), name or ""),
                "url": _clean_name(rec.get("url")),
                "city": _clean_name(rec.get("place_city")),
                "country": _clean_name(rec.get("place_country")),
                "location_id": loc_i,
                "source": "event_editions_month_only" if stats_only else "event_editions",
                "year": year_i,
                "stats_only": stats_only,
                "has_results": result_rows > 0,
            }
        )
    return rows


def _city_from_location_raw(raw: Any) -> str | None:
    """First comma segment of schedule location_raw (e.g. Dallas, TX, United States)."""
    text = _clean_name(raw)
    if not text:
        return None
    return text.split(",")[0].strip() or None


def _is_ucwdc_dallas_worlds_title(name: str | None) -> bool:
    """True for the Dallas Championship series title (not Orlando 'Worlds UCWDC')."""
    cleaned = _clean_name(name)
    if not cleaned:
        return False
    low = cleaned.lower()
    if low == "worlds ucwdc":
        return False
    return "ucwdc" in low and "country dance world championship" in low


def _correct_ucwdc_worlds_event_ids(rows: list[dict]) -> None:
    """Keep Dallas Worlds on results id 75; do not attach to Orlando id 152.

    Schedule/calendar historically matched ``ucwdcworlds.com`` + plural
    Championships title onto catalog id 152 (Worlds UCWDC, Orlando 2009–2015).
    Those are separate series — remapped here by title.
    """
    for row in rows:
        if not _is_ucwdc_dallas_worlds_title(row.get("name")):
            continue
        eid = row.get("event_id")
        try:
            eid_i = int(eid) if eid is not None else None
        except (TypeError, ValueError):
            eid_i = None
        if eid_i in (None, 152, 480):
            row["event_id"] = 75
            if "championships" in str(row.get("name") or "").lower():
                row["name"] = "UCWDC Country Dance World Championship"


def _rows_from_scheduled(data_dir: Path) -> list[dict]:
    path = data_dir / "scheduled_events.csv"
    if not path.exists():
        return []
    df = pd.read_csv(path)
    rows: list[dict] = []
    for rec in df.to_dict(orient="records"):
        start = _parse_date(rec.get("start_date"))
        if start is None:
            continue
        if _truthy(rec.get("canceled")):
            status = STATUS_CANCELLED
        elif _truthy(rec.get("on_hiatus")):
            status = STATUS_HIATUS
        else:
            status = STATUS_CONFIRMED if _truthy(rec.get("confirmed")) else STATUS_EXPECTED
        eid = rec.get("canonical_event_id")
        try:
            eid_i = int(eid) if eid is not None and not pd.isna(eid) else None
        except (TypeError, ValueError):
            eid_i = None
        name = _clean_name(rec.get("event_name")) or _clean_name(rec.get("canonical_name"))
        status_flags = rec.get("status_event") or rec.get("registry_trial_status")
        kind_from_schedule = _status_flags_say_trial(status_flags)
        year_raw = rec.get("results_year")
        try:
            year_i = int(year_raw) if year_raw is not None and not pd.isna(year_raw) else start.year
        except (TypeError, ValueError):
            year_i = start.year
        loc_raw = rec.get("location_id")
        try:
            loc_i = int(loc_raw) if loc_raw is not None and not pd.isna(loc_raw) else None
        except (TypeError, ValueError):
            loc_i = None
        rows.append(
            {
                "event_id": eid_i,
                "name": name,
                "start_date": start,
                "end_date": _parse_date(rec.get("end_date")),
                "status": status,
                "kind": _kind_from_status_event(status_flags, name or ""),
                "kind_from_schedule": kind_from_schedule,
                "url": _clean_name(rec.get("url")),
                "city": _city_from_location_raw(rec.get("location_raw")),
                "country": _clean_name(rec.get("country")),
                "location_id": loc_i,
                "source": "scheduled_events",
                "year": year_i,
            }
        )
    return rows


def _inactive_event_ids(catalog: pd.DataFrame) -> set[int]:
    if catalog.empty or "registry_status" not in catalog.columns:
        return set()
    out: set[int] = set()
    for rec in catalog.to_dict(orient="records"):
        status = str(rec.get("registry_status") or "").strip().lower()
        if status not in {"inactive", "merged"}:
            continue
        eid = rec.get("event_id")
        if eid is None or (isinstance(eid, float) and pd.isna(eid)):
            continue
        out.add(int(eid))
    return out


def _prefer_row(existing: dict, new: dict) -> dict:
    """Merge duplicate event_id+year preferring confirmed schedule over expected."""
    rank = {
        STATUS_CANCELLED: 4,
        STATUS_HIATUS: 4,
        STATUS_CONFIRMED: 3,
        STATUS_EXPECTED: 1,
    }
    src_rank = {
        "scheduled_events": 4,
        "edition_calendar_dates": 3,
        "operator_override": 3,
        "event_editions": 2,
        "event_editions_month_only": 1,
        "expected_yoy": 0,
    }
    e_score = (
        rank.get(existing["status"], 0),
        src_rank.get(existing.get("source"), 0),
        0 if existing.get("stats_only") else 1,
    )
    n_score = (
        rank.get(new["status"], 0),
        src_rank.get(new.get("source"), 0),
        0 if new.get("stats_only") else 1,
    )
    winner = dict(new if n_score >= e_score else existing)
    loser = existing if n_score >= e_score else new
    # Keep richer geo/url/end from either
    for key in ("url", "city", "country", "location_id", "kind", "name", "end_date"):
        if not winner.get(key) and loser.get(key):
            winner[key] = loser[key]
    if winner.get("stats_only") and not loser.get("stats_only"):
        winner["stats_only"] = False
        winner["source"] = loser.get("source") or winner.get("source")
    if loser.get("has_results"):
        winner["has_results"] = True
    # Do not inherit kind_from_schedule from a losing same-year sibling
    # (e.g. Trial schedule in Sep vs hiatus edition in Dec for one event_id).
    if not winner.get("kind_from_schedule"):
        winner.pop("kind_from_schedule", None)
    return winner


def _fill_missing_end_dates(rows: list[dict]) -> None:
    """Fill blank end_date from prior edition duration, else Thu–Sun weekend Sunday.

    WSDC calendar scrapes sometimes publish only a start day (e.g. Chicago Classic
    2026-03-19). Without an end, the year grid paints a single-day spike.
    """
    duration_by_eid: dict[int, int] = {}
    for row in rows:
        if row.get("stats_only"):
            continue
        eid = row.get("event_id")
        start = row.get("start_date")
        end = row.get("end_date")
        if eid is None or not isinstance(start, date) or not isinstance(end, date):
            continue
        if end < start:
            continue
        days = (end - start).days
        prev = duration_by_eid.get(int(eid))
        # Prefer longer observed span (weekend festivals), keep latest overwrite
        if prev is None or days >= prev:
            duration_by_eid[int(eid)] = days

    for row in rows:
        if row.get("stats_only"):
            continue
        start = row.get("start_date")
        if not isinstance(start, date):
            continue
        if isinstance(row.get("end_date"), date):
            continue
        eid = row.get("event_id")
        if eid is not None and int(eid) in duration_by_eid:
            row["end_date"] = start + timedelta(days=duration_by_eid[int(eid)])
            continue
        _thu, sun = weekend_bounds(start)
        row["end_date"] = sun if sun >= start else start


def _mark_has_results(rows: list[dict], data_dir: Path) -> None:
    """Flag calendar rows whose (event_id, year) has competition results."""
    path = Path(data_dir) / "event_editions.csv"
    keys: set[tuple[int, int]] = set()
    if path.exists():
        df = pd.read_csv(path)
        for rec in df.to_dict(orient="records"):
            try:
                rr = int(float(rec.get("result_rows") or 0))
            except (TypeError, ValueError):
                rr = 0
            if rr <= 0:
                continue
            try:
                eid = int(rec["event_id"])
                year = int(rec["event_year"])
            except (TypeError, ValueError, KeyError):
                continue
            keys.add((eid, year))
    for row in rows:
        eid = row.get("event_id")
        y = _row_year(row)
        if eid is None or y is None:
            continue
        if (int(eid), y) in keys:
            row["has_results"] = True


def _resolve_merge_event_id(eid: int | None) -> int | None:
    if eid is None:
        return None
    seen: set[int] = set()
    cur = int(eid)
    while cur in MERGE_EVENT_ID_MAP and cur not in seen:
        seen.add(cur)
        cur = int(MERGE_EVENT_ID_MAP[cur])
    return cur


def _apply_year_aware_series_names(rows: list[dict]) -> None:
    """Set display name (+ stable id) from EVENT_NAME_YEAR_SPLITS.

    Catalog ``canonical_name`` reflects the *current* WSDC registry label, which
    is wrong for earlier editions when WSDC reuses an id or the series rebrands.
    Call after merge/dedupe so ghosts collapse first.
    """
    if not rows or not EVENT_NAME_YEAR_SPLITS:
        return
    for row in rows:
        year = _row_year(row)
        if year is None:
            continue
        name = _clean_name(row.get("name"))
        eid = row.get("event_id")
        try:
            eid_i = int(eid) if eid is not None else None
        except (TypeError, ValueError):
            eid_i = None
        name_l = name.lower() if name else ""
        for rule in EVENT_NAME_YEAR_SPLITS:
            sources = {str(s).strip().lower() for s in rule["sources"]}  # type: ignore[arg-type]
            early_id = rule.get("early_event_id")
            late_id = rule.get("late_event_id")
            id_match = eid_i is not None and (
                (early_id is not None and eid_i == int(early_id))
                or (late_id is not None and eid_i == int(late_id))
            )
            name_match = bool(name_l) and name_l in sources
            if not (id_match or name_match):
                continue
            early_max = int(rule["early_year_max"])  # type: ignore[arg-type]
            late_min = int(rule["late_year_min"])  # type: ignore[arg-type]
            if year <= early_max:
                row["name"] = str(rule["early_name"])
                if early_id is not None:
                    row["event_id"] = int(early_id)
            elif year >= late_min:
                row["name"] = str(rule["late_name"])
                if late_id is not None:
                    row["event_id"] = int(late_id)
            break


def _drop_redundant_stats_only(rows: list[dict]) -> list[dict]:
    """Drop month-placeholder editions when a day-precision row exists for same id+year.

    ``_dedupe_rows`` only merges same weekend; results often use the 1st of the
    month while the calendar has the real weekend later in the month.
    """
    day_keys: set[tuple[int, int]] = set()
    for row in rows:
        if row.get("stats_only"):
            continue
        eid = row.get("event_id")
        year = _row_year(row)
        if eid is None or year is None:
            continue
        day_keys.add((int(eid), int(year)))
    out: list[dict] = []
    for row in rows:
        if row.get("stats_only"):
            eid = row.get("event_id")
            year = _row_year(row)
            if (
                eid is not None
                and year is not None
                and (int(eid), int(year)) in day_keys
            ):
                continue
        out.append(row)
    return out


def _alias_event_name(name: str | None) -> str | None:
    cleaned = _clean_name(name)
    if not cleaned:
        return None
    return _NAME_ALIAS_LOOKUP.get(cleaned.lower(), cleaned)


def _fingerprint_event_name(name: str | None) -> str:
    """Loose token fingerprint for cross-source near-duplicate matching."""
    text = _alias_event_name(name) or ""
    tokens = [
        tok
        for tok in "".join(ch if ch.isalnum() else " " for ch in text.lower()).split()
        if tok and tok not in _NAME_STOPWORDS
    ]
    return " ".join(tokens)


def _catalog_quality(eid: int | None, cat_by_id: dict[int, dict]) -> tuple[int, int]:
    if eid is None or eid not in cat_by_id:
        return (0, 0)
    cat = cat_by_id[eid]
    status = str(cat.get("registry_status") or "").strip().lower()
    active = 0 if status in {"inactive", "merged"} else 1
    try:
        editions = int(cat.get("edition_count") or 0)
    except (TypeError, ValueError):
        editions = 0
    return (active, editions)


def _canonicalize_calendar_rows(rows: list[dict], catalog: pd.DataFrame) -> None:
    """Remap ghost event ids / alias names onto catalog identities before dedupe."""
    cat_by_id: dict[int, dict] = {}
    cat_by_name: dict[str, dict] = {}
    if not catalog.empty:
        for rec in catalog.to_dict(orient="records"):
            eid = rec.get("event_id")
            if eid is None or (isinstance(eid, float) and pd.isna(eid)):
                continue
            eid_i = int(eid)
            cat_by_id[eid_i] = rec
            cname = _clean_name(rec.get("canonical_name"))
            if cname:
                cat_by_name[cname.lower()] = rec

    for row in rows:
        eid = row.get("event_id")
        if eid is not None:
            row["event_id"] = _resolve_merge_event_id(int(eid))
        aliased = _alias_event_name(row.get("name"))
        if aliased:
            row["name"] = aliased
            cat = cat_by_name.get(aliased.lower())
            if cat is not None:
                cat_eid = int(cat["event_id"])
                cur = row.get("event_id")
                if cur is None or _catalog_quality(cat_eid, cat_by_id) >= _catalog_quality(
                    int(cur) if cur is not None else None, cat_by_id
                ):
                    row["event_id"] = cat_eid


def _prefer_calendar_row(
    existing: dict,
    new: dict,
    *,
    cat_by_id: dict[int, dict] | None = None,
) -> dict:
    winner = _prefer_row(existing, new)
    if not cat_by_id:
        return winner
    candidates = [existing, new]
    best = max(
        candidates,
        key=lambda r: (
            _catalog_quality(
                int(r["event_id"]) if r.get("event_id") is not None else None,
                cat_by_id,
            ),
            1 if r.get("end_date") else 0,
            1 if r.get("url") else 0,
        ),
    )
    if best.get("event_id") is not None:
        winner["event_id"] = best["event_id"]
        cat = cat_by_id.get(int(best["event_id"]))
        if cat is not None:
            cname = _clean_name(cat.get("canonical_name"))
            wname = _clean_name(winner.get("name"))
            # Keep live schedule/calendar renames (SwingCo vs catalog SwingCouver)
            if cname and not (
                wname
                and winner.get("source") in {"scheduled_events", "edition_calendar_dates"}
                and _fingerprint_event_name(wname) != _fingerprint_event_name(cname)
            ):
                winner["name"] = cname
    return winner


def _dedupe_rows(rows: list[dict], *, cat_by_id: dict[int, dict] | None = None) -> list[dict]:
    by_key: dict[tuple, dict] = {}
    for row in rows:
        eid = row.get("event_id")
        start = row.get("start_date")
        if not isinstance(start, date):
            continue
        row_year = _row_year(row)
        if row_year is None:
            continue
        # Keep distinct weekends for the same series (relocation / false hiatus
        # matches must not erase a real scheduled weekend in the same year).
        # Use edition/results year so Dec→Jan weekends dedupe inside the results year.
        key = (
            eid if eid is not None else row.get("name"),
            row_year,
            weekend_key(start),
        )
        if key in by_key:
            by_key[key] = _prefer_calendar_row(by_key[key], row, cat_by_id=cat_by_id)
        else:
            by_key[key] = row
    return list(by_key.values())


def _dedupe_weekend_name_collisions(
    rows: list[dict],
    *,
    cat_by_id: dict[int, dict] | None = None,
) -> list[dict]:
    """Merge same-weekend near-duplicates that still carry different event_ids.

    Cross-source scrapes often emit ghost ids / \"The …\" title variants for one
    festival (Paris Swing Classic ×3, Boston Tea Party vs The Boston Tea Party).
    """
    by_key: dict[tuple, dict] = {}
    passthrough: list[dict] = []
    for row in rows:
        start = row.get("start_date")
        if not isinstance(start, date):
            continue
        fp = _fingerprint_event_name(row.get("name"))
        if not fp:
            passthrough.append(row)
            continue
        key = (start.year, weekend_key(start), fp)
        if key in by_key:
            by_key[key] = _prefer_calendar_row(by_key[key], row, cat_by_id=cat_by_id)
        else:
            by_key[key] = row
    return passthrough + list(by_key.values())


def _enrich_geo(
    rows: list[dict],
    locations: pd.DataFrame,
    catalog: pd.DataFrame,
    *,
    location_id_by_event: dict[int, int] | None = None,
) -> None:
    loc_by_id = {}
    if not locations.empty:
        for rec in locations.to_dict(orient="records"):
            lid = rec.get("location_id")
            if pd.isna(lid):
                continue
            loc_by_id[int(lid)] = rec
    cat_by_id = {}
    if not catalog.empty:
        for rec in catalog.to_dict(orient="records"):
            eid = rec.get("event_id")
            if pd.isna(eid):
                continue
            cat_by_id[int(eid)] = rec
    loc_by_event = location_id_by_event or {}
    coords_by_place = _coords_by_city_country(locations)

    for row in rows:
        eid = row.get("event_id")
        if eid is not None and eid in cat_by_id:
            cat = cat_by_id[eid]
            if not _clean_name(row.get("name")):
                row["name"] = _clean_name(cat.get("canonical_name"))
            if not row.get("url"):
                row["url"] = _clean_name(cat.get("url"))
            if not row.get("city"):
                row["city"] = _clean_name(cat.get("typical_city"))
            if not row.get("country"):
                row["country"] = _clean_name(cat.get("typical_country"))
        if row.get("location_id") is None and eid is not None:
            inherited = loc_by_event.get(int(eid))
            if inherited is not None:
                row["location_id"] = inherited
        lid = row.get("location_id")
        if lid is not None and lid in loc_by_id:
            loc = loc_by_id[lid]
            if not row.get("city"):
                row["city"] = _clean_name(loc.get("event_city"))
            if not row.get("country"):
                row["country"] = _clean_name(loc.get("event_country"))
            if _truthy(loc.get("coordinates_valid")):
                try:
                    lat = float(loc["latitude"])
                    lon = float(loc["longitude"])
                except (TypeError, ValueError, KeyError):
                    lat = lon = None
                row["lat"] = lat
                row["lon"] = lon
            else:
                row["lat"] = None
                row["lon"] = None
        else:
            row.setdefault("lat", None)
            row.setdefault("lon", None)
        # City/country fallback when location_id is missing or coords invalid
        if row.get("lat") is None or row.get("lon") is None:
            place = (_norm_place(row.get("city")), _norm_place(row.get("country")))
            if place[0] and place[1] and place in coords_by_place:
                row["lat"], row["lon"] = coords_by_place[place]
        # Normalize name after enrichment
        row["name"] = _clean_name(row.get("name"))


def _calendar_continent(country: str | None) -> str | None:
    """Map country to the four calendar continents (America/Europe/Asia/Australia)."""
    if not _clean_name(country):
        return None
    raw = continent_for_country(country)
    if raw == "South America":
        return "America"
    if raw in CALENDAR_CONTINENTS:
        return raw
    return "America"


def _row_year(row: dict) -> int | None:
    year = row.get("year")
    if year is not None:
        try:
            return int(year)
        except (TypeError, ValueError):
            pass
    start = row.get("start_date")
    if isinstance(start, date):
        return start.year
    return None


def _series_linked_ids(event_id: int | None) -> set[int]:
    """Return all known linked ids in the same rebranded series."""
    if event_id is None:
        return set()
    eid = int(event_id)
    linked = {eid}
    nxt = SERIES_SUCCESSOR_MAP.get(eid)
    if nxt is not None:
        linked.add(int(nxt))
    for src, dst in SERIES_SUCCESSOR_MAP.items():
        if int(dst) == eid:
            linked.add(int(src))
    return linked


def _latest_confirmed_priors(
    confirmed_rows: list[dict],
    *,
    before_year: int,
) -> list[dict]:
    """Most recent confirmed edition per event_id with row year < before_year."""
    best: dict[int, dict] = {}
    for row in confirmed_rows:
        eid = row.get("event_id")
        start = row.get("start_date")
        row_year = _row_year(row)
        if eid is None or not isinstance(start, date):
            continue
        if row_year is None or row_year >= before_year:
            continue
        prev = best.get(eid)
        if prev is None or start > prev["start_date"]:
            best[int(eid)] = row
    return list(best.values())


def _ids_blocked_by_terminal(
    rows: list[dict],
    *,
    before_year: int,
) -> set[int]:
    """Event ids whose latest confirmed/cancelled/hiatus before ``before_year`` is terminal."""
    latest: dict[int, tuple[date, str]] = {}
    for row in rows:
        eid = row.get("event_id")
        start = row.get("start_date")
        status = row.get("status")
        row_year = _row_year(row)
        if eid is None or not isinstance(start, date):
            continue
        if row_year is None or row_year >= before_year:
            continue
        if status not in {STATUS_CONFIRMED, STATUS_CANCELLED, STATUS_HIATUS}:
            continue
        eid_i = int(eid)
        prev = latest.get(eid_i)
        if prev is None or start > prev[0]:
            latest[eid_i] = (start, status)
    blocked = {
        eid
        for eid, (_start, status) in latest.items()
        if status in {STATUS_CANCELLED, STATUS_HIATUS}
    }
    out: set[int] = set()
    for eid in blocked:
        out.update(_series_linked_ids(eid))
    return out


def _uid_token_for_row(row: dict) -> str:
    """Stable middle segment for calendar row ``id``.

    Registry rows use ``event_id``. Unlinked trials (``event_id`` null) used to
    share ``x`` and collided when two trials started on the same day — L2 hover
    / select / marker lookup all key off ``id``.

    Unlinked tokens are prefixed with ``t-`` so a numeric-only slug cannot
    collide with a real ``event_id`` token on the same date.
    """
    eid = row.get("event_id")
    if eid is not None:
        try:
            return str(int(eid))
        except (TypeError, ValueError):
            return str(eid)
    parts = [
        str(row.get("name") or "").strip().lower(),
        str(row.get("city") or "").strip().lower(),
        str(row.get("country") or "").strip().lower(),
    ]
    raw = "-".join(p for p in parts if p)
    # Fold diacritics (Köln → koln) before ASCII slugify.
    raw = unicodedata.normalize("NFKD", raw)
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    token = slug[:62] if slug else "x"
    return f"t-{token}"


def _serialize_event(row: dict) -> dict:
    start: date = row["start_date"]
    end = row.get("end_date")
    thu, sun = weekend_bounds(start)
    eid = row.get("event_id")
    status = row["status"]
    uid = f"{status}:{_uid_token_for_row(row)}:{start.isoformat()}"
    country = row.get("country")
    year = row.get("year")
    try:
        year_i = int(year)
    except (TypeError, ValueError):
        year_i = start.year
    out = {
        "id": uid,
        "event_id": eid,
        "name": row.get("name") or "Unknown event",
        "start_date": start.isoformat(),
        "end_date": end.isoformat() if isinstance(end, date) else None,
        "weekend_start": thu.isoformat(),
        "weekend_end": sun.isoformat(),
        "weekend_key": weekend_key(start),
        "status": status,
        "kind": row.get("kind") or KIND_REGISTRY,
        "city": row.get("city"),
        "country": country,
        "continent": _calendar_continent(country),
        "lat": row.get("lat"),
        "lon": row.get("lon"),
        "url": row.get("url"),
        "year": year_i,
        "source": row.get("source"),
    }
    if row.get("projected_from_year") is not None:
        out["projected_from_year"] = row["projected_from_year"]
        out["projected_from_start"] = row.get("projected_from_start")
    if row.get("stats_only"):
        out["stats_only"] = True
    if row.get("has_results"):
        out["has_results"] = True
    return out


def _drop_stale_expected(
    rows: list[dict],
    as_of: date,
    *,
    grace_days: int = EXPECTED_STALE_GRACE_DAYS,
) -> list[dict]:
    """Remove expected rows for finished periods (past year or past+grace)."""
    out: list[dict] = []
    for row in rows:
        if row.get("status") != STATUS_EXPECTED:
            out.append(row)
            continue
        start = row.get("start_date")
        if not isinstance(start, date):
            continue
        end = row.get("end_date") if isinstance(row.get("end_date"), date) else None
        if is_stale_expected(start=start, end=end, as_of=as_of, grace_days=grace_days):
            continue
        out.append(row)
    return out


def build_year_event_calendar(
    data_dir: Path | str,
    *,
    as_of: date | None = None,
    year_radius: int = 2,
    expected_horizon_years: int | None = None,
) -> dict:
    """Assemble payload for ``events_year_calendar.json``.

    Expected (YoY) projections cover ``as_of.year .. as_of.year +
    expected_horizon_years`` (default: same span as ``year_radius`` so future
    selector years get gray expected pins from the latest confirmed edition).
    Years beyond that horizon only keep ``scheduled_events`` rows.
    """
    data_dir = Path(data_dir)
    as_of = as_of or date.today()
    if expected_horizon_years is None:
        expected_horizon_years = year_radius
    years = _year_window(as_of, radius=year_radius)
    expected_years = {
        y for y in years if as_of.year <= y <= as_of.year + expected_horizon_years
    }
    far_years = {y for y in years if y > as_of.year + expected_horizon_years}

    locations = _load_locations(data_dir)
    catalog = _load_catalog(data_dir)
    inactive_ids = _inactive_event_ids(catalog)
    location_id_by_event = _location_id_by_event(data_dir)
    cat_by_id: dict[int, dict] = {}
    if not catalog.empty:
        for rec in catalog.to_dict(orient="records"):
            eid = rec.get("event_id")
            if eid is None or (isinstance(eid, float) and pd.isna(eid)):
                continue
            cat_by_id[int(eid)] = rec

    base_rows = (
        _rows_from_edition_calendar_dates(data_dir)
        + _rows_from_operator_overrides()
        + _rows_from_editions(data_dir)
        + _rows_from_scheduled(data_dir)
    )
    _canonicalize_calendar_rows(base_rows, catalog)
    _correct_ucwdc_worlds_event_ids(base_rows)
    # Far future: only published schedule (avoid long-range calendar scrape noise)
    filtered_base: list[dict] = []
    for row in base_rows:
        y = _row_year(row)
        if y is None:
            continue
        if y in far_years and row.get("source") != "scheduled_events":
            continue
        filtered_base.append(row)
    merged = _dedupe_weekend_name_collisions(
        _dedupe_rows(filtered_base, cat_by_id=cat_by_id),
        cat_by_id=cat_by_id,
    )
    _apply_year_aware_series_names(merged)
    merged = _drop_redundant_stats_only(merged)

    # Event-ids that already have a non-expected status in each year
    skip_by_year: dict[int, set] = {y: set() for y in years}
    confirmed_by_year: dict[int, dict] = {y: {} for y in years}
    confirmed_by_event: dict[int, list[date]] = {}
    for row in merged:
        start = row["start_date"]
        y = _row_year(row)
        if y is None:
            continue
        if y not in skip_by_year:
            continue
        eid = row.get("event_id")
        if eid is None:
            continue
        if row["status"] in {STATUS_CONFIRMED, STATUS_CANCELLED, STATUS_HIATUS}:
            skip_by_year[y].update(_series_linked_ids(int(eid)))
        if row["status"] == STATUS_CONFIRMED:
            confirmed_by_year[y].setdefault(eid, []).append(start)
            confirmed_by_event.setdefault(int(eid), []).append(start)

    # Expected from latest confirmed edition before target year (WSDC ±1 week rule
    # vs any confirmed start — including year-boundary moves like NYE → early Jan).
    expected_rows: list[dict] = []
    prior_pool = [
        r
        for r in merged
        if r["status"] == STATUS_CONFIRMED
        and not r.get("stats_only")
        and isinstance(r.get("start_date"), date)
        and r.get("event_id") not in inactive_ids
    ]
    for y in sorted(expected_years):
        priors = _latest_confirmed_priors(prior_pool, before_year=y)
        blocked = _ids_blocked_by_terminal(merged, before_year=y)
        skip_ids = set(skip_by_year.get(y, set())) | inactive_ids | blocked
        stubs = iter_expected_candidates(
            priors,
            target_year=y,
            skip_event_ids=skip_ids,
        )
        kept = []
        for stub in stubs:
            eid = stub.get("event_id")
            if eid is None or eid in inactive_ids:
                continue
            hit = match_expected_to_confirmed(
                event_id=eid,
                projected_start=stub["start_date"],
                confirmed_by_event=confirmed_by_event,
                window_days=EXPECTED_WINDOW_DAYS,
            )
            if hit is not None:
                continue
            if is_stale_expected(
                start=stub["start_date"],
                end=stub.get("end_date") if isinstance(stub.get("end_date"), date) else None,
                as_of=as_of,
            ):
                continue
            kept.append(stub)
        expected_rows.extend(kept)

    all_rows = _dedupe_weekend_name_collisions(
        _dedupe_rows(merged + expected_rows, cat_by_id=cat_by_id),
        cat_by_id=cat_by_id,
    )
    _enrich_geo(
        all_rows,
        locations,
        catalog,
        location_id_by_event=location_id_by_event,
    )
    _fill_missing_end_dates(all_rows)
    first_points_year = _first_points_year_by_event(data_dir, catalog)
    _apply_kind_rules(
        all_rows,
        first_points_year=first_points_year,
        catalog=catalog,
    )
    _mark_has_results(all_rows, data_dir)
    _apply_year_aware_series_names(all_rows)
    all_rows = _drop_redundant_stats_only(all_rows)

    # Drop nameless rows after catalog enrichment
    named_rows = [r for r in all_rows if _clean_name(r.get("name"))]
    named_rows = _drop_stale_expected(named_rows, as_of)

    in_window = [r for r in named_rows if (_row_year(r) in years)]
    in_window.sort(key=lambda r: (r["start_date"], r.get("name") or ""))

    events = [_serialize_event(r) for r in in_window]
    by_year = {str(y): sum(1 for e in events if e["year"] == y) for y in years}
    # Omit empty years from the selector (e.g. 2024 with no day-precision dates)
    years_with_data = [y for y in years if by_year.get(str(y), 0) > 0]
    default_year = as_of.year if as_of.year in years_with_data else (
        years_with_data[0] if years_with_data else as_of.year
    )

    return {
        "as_of": as_of.isoformat(),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "years": years_with_data,
        "default_year": default_year,
        "expected_window_days": EXPECTED_WINDOW_DAYS,
        "expected_horizon_years": expected_horizon_years,
        "continents": list(CALENDAR_CONTINENTS),
        "weekend": {"start_weekday": "thu", "end_weekday": "sun"},
        "counts_by_year": {str(y): by_year[str(y)] for y in years_with_data},
        "disclaimer": {
            "en": "Expected events are projected from the latest confirmed edition (±1 week per WSDC Registry Rules) for the current year and near-future years in the selector. They stay unconfirmed until published on the WSDC calendar; hiatus/cancelled stops the projection.",
            "ru": "Expected-ивенты — проекция с последней подтверждённой edition (±1 неделя по правилам WSDC) на текущий и ближайшие годы в селекторе. Неподтверждены, пока не появятся в календаре WSDC; hiatus/отмена останавливает проекцию.",
            "es": "Los eventos expected se proyectan desde la última edición confirmada (±1 semana según reglas WSDC) para el año actual y años cercanos del selector. Siguen sin confirmar hasta publicarse en el calendario WSDC; hiatus/cancelación detiene la proyección.",
        },
        "events": events,
    }


def write_year_event_calendar(payload: dict, output: Path) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def spike_expected_accuracy(
    data_dir: Path | str,
    *,
    prior_year: int,
    target_year: int,
) -> dict:
    """Compare YoY expected projections vs confirmed starts in target_year."""
    data_dir = Path(data_dir)
    payload_prior = build_year_event_calendar(
        data_dir,
        as_of=date(target_year, 6, 15),
        year_radius=max(2, abs(target_year - prior_year) + 1),
    )
    events = payload_prior["events"]
    confirmed_target = [
        e for e in events if e["year"] == target_year and e["status"] == STATUS_CONFIRMED and e.get("event_id")
    ]
    confirmed_by = {}
    for e in confirmed_target:
        confirmed_by.setdefault(e["event_id"], []).append(date.fromisoformat(e["start_date"]))

    prior_confirmed = [
        e for e in events if e["year"] == prior_year and e["status"] == STATUS_CONFIRMED and e.get("event_id")
    ]

    matched = 0
    missed = 0  # prior series with no target match within window
    for e in prior_confirmed:
        projected = project_start_to_year(date.fromisoformat(e["start_date"]), target_year)
        hit = match_expected_to_confirmed(
            event_id=e["event_id"],
            projected_start=projected,
            confirmed_by_event=confirmed_by,
        )
        if hit is not None:
            matched += 1
        else:
            # Still "ok" if target has cancelled/hiatus for same id
            target_statuses = [
                x["status"]
                for x in events
                if x["year"] == target_year and x.get("event_id") == e["event_id"]
            ]
            if any(s in {STATUS_CANCELLED, STATUS_HIATUS, STATUS_CONFIRMED} for s in target_statuses):
                if STATUS_CONFIRMED in target_statuses and hit is None:
                    # confirmed but outside ±7d — date moved
                    missed += 1
                # cancelled/hiatus: not a false expected
            else:
                missed += 1

    # False positives: would emit expected while nothing (or only far confirmed)
    would_expected = 0
    false_positive_far = 0
    skip_ids = {
        e["event_id"]
        for e in events
        if e["year"] == target_year
        and e["status"] in {STATUS_CONFIRMED, STATUS_CANCELLED, STATUS_HIATUS}
        and e.get("event_id") is not None
    }
    for e in prior_confirmed:
        eid = e["event_id"]
        if eid in skip_ids:
            # Check if confirmed but outside window → bad skip? skip means no expected
            projected = project_start_to_year(date.fromisoformat(e["start_date"]), target_year)
            hit = match_expected_to_confirmed(
                event_id=eid,
                projected_start=projected,
                confirmed_by_event=confirmed_by,
            )
            if hit is None and eid in confirmed_by:
                false_positive_far += 1  # moved >7d; we won't show expected (good) but calendar gap
            continue
        would_expected += 1

    return {
        "prior_year": prior_year,
        "target_year": target_year,
        "prior_confirmed": len(prior_confirmed),
        "target_confirmed": len(confirmed_target),
        "matched_within_window": matched,
        "prior_without_near_match": missed,
        "would_emit_expected": would_expected,
        "confirmed_outside_window": false_positive_far,
        "match_rate": round(matched / len(prior_confirmed), 4) if prior_confirmed else None,
    }

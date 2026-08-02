"""Build events_year_calendar.json payload from pipeline CSVs."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from transform.year_event_calendar.expected import (
    EXPECTED_WINDOW_DAYS,
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


def _rows_from_edition_calendar_dates(data_dir: Path) -> list[dict]:
    path = data_dir / "edition_calendar_dates.csv"
    if not path.exists():
        return []
    df = pd.read_csv(path)
    rows: list[dict] = []
    for rec in df.to_dict(orient="records"):
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
        name = _clean_name(rec.get("event_name")) or _clean_name(rec.get("calendar_title"))
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
                "year": start.year,
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
        if start is None:
            continue
        # Month-only placeholders (YYYY-MM-01 with no real calendar day) — skip
        # when date_source is missing and day is 1 and no calendar_status.
        # Keep rows that have calendar_status or date_source day.
        date_source = str(rec.get("date_source") or "").strip().lower()
        cal_status = _norm_status_calendar(rec.get("calendar_status"))
        if start.day == 1 and not cal_status and date_source not in {
            "wsdc_calendar",
            "wsdc_events_list",
            "day",
        }:
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
                "source": "event_editions",
                "year": start.year,
            }
        )
    return rows


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
        elif _truthy(rec.get("confirmed")):
            status = STATUS_CONFIRMED
        else:
            status = STATUS_EXPECTED
        eid = rec.get("canonical_event_id")
        try:
            eid_i = int(eid) if eid is not None and not pd.isna(eid) else None
        except (TypeError, ValueError):
            eid_i = None
        name = _clean_name(rec.get("event_name")) or _clean_name(rec.get("canonical_name"))
        rows.append(
            {
                "event_id": eid_i,
                "name": name,
                "start_date": start,
                "end_date": _parse_date(rec.get("end_date")),
                "status": status,
                "kind": _kind_from_status_event(
                    rec.get("status_event") or rec.get("registry_trial_status"),
                    name or "",
                ),
                "url": _clean_name(rec.get("url")),
                "city": None,
                "country": _clean_name(rec.get("country")),
                "location_id": None,
                "source": "scheduled_events",
                "year": start.year,
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
        "event_editions": 2,
        "expected_yoy": 0,
    }
    e_score = (rank.get(existing["status"], 0), src_rank.get(existing.get("source"), 0))
    n_score = (rank.get(new["status"], 0), src_rank.get(new.get("source"), 0))
    winner = new if n_score >= e_score else existing
    # Keep richer geo/url from either
    for key in ("url", "city", "country", "location_id", "kind", "name"):
        if not winner.get(key) and existing.get(key):
            winner[key] = existing[key]
        if not winner.get(key) and new.get(key):
            winner[key] = new[key]
    return winner


def _dedupe_rows(rows: list[dict]) -> list[dict]:
    by_key: dict[tuple, dict] = {}
    for row in rows:
        eid = row.get("event_id")
        start = row.get("start_date")
        if not isinstance(start, date):
            continue
        key = (eid if eid is not None else row.get("name"), start.year)
        if key in by_key:
            by_key[key] = _prefer_row(by_key[key], row)
        else:
            by_key[key] = row
    return list(by_key.values())


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


def _serialize_event(row: dict) -> dict:
    start: date = row["start_date"]
    end = row.get("end_date")
    thu, sun = weekend_bounds(start)
    eid = row.get("event_id")
    status = row["status"]
    uid = f"{status}:{eid if eid is not None else 'x'}:{start.isoformat()}"
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
        "country": row.get("country"),
        "lat": row.get("lat"),
        "lon": row.get("lon"),
        "url": row.get("url"),
        "year": start.year,
        "source": row.get("source"),
    }
    if row.get("projected_from_year") is not None:
        out["projected_from_year"] = row["projected_from_year"]
        out["projected_from_start"] = row.get("projected_from_start")
    return out


def build_year_event_calendar(
    data_dir: Path | str,
    *,
    as_of: date | None = None,
    year_radius: int = 2,
    expected_horizon_years: int = 0,
) -> dict:
    """Assemble payload for ``events_year_calendar.json``.

    Expected (YoY) projections are limited to ``as_of.year .. as_of.year +
    expected_horizon_years`` (default: current year only) so future years are
    not flooded with gray placeholders. Years beyond that horizon only keep
    ``scheduled_events`` rows.
    """
    data_dir = Path(data_dir)
    as_of = as_of or date.today()
    years = _year_window(as_of, radius=year_radius)
    expected_years = {
        y for y in years if as_of.year <= y <= as_of.year + expected_horizon_years
    }
    far_years = {y for y in years if y > as_of.year + expected_horizon_years}

    locations = _load_locations(data_dir)
    catalog = _load_catalog(data_dir)
    inactive_ids = _inactive_event_ids(catalog)
    location_id_by_event = _location_id_by_event(data_dir)

    base_rows = (
        _rows_from_edition_calendar_dates(data_dir)
        + _rows_from_editions(data_dir)
        + _rows_from_scheduled(data_dir)
    )
    # Far future: only published schedule (avoid long-range calendar scrape noise)
    filtered_base: list[dict] = []
    for row in base_rows:
        y = row["start_date"].year
        if y in far_years and row.get("source") != "scheduled_events":
            continue
        filtered_base.append(row)
    merged = _dedupe_rows(filtered_base)

    # Event-ids that already have a non-expected status in each year
    skip_by_year: dict[int, set] = {y: set() for y in years}
    confirmed_by_year: dict[int, dict] = {y: {} for y in years}
    for row in merged:
        start = row["start_date"]
        y = start.year
        if y not in skip_by_year:
            continue
        eid = row.get("event_id")
        if eid is None:
            continue
        if row["status"] in {STATUS_CONFIRMED, STATUS_CANCELLED, STATUS_HIATUS}:
            skip_by_year[y].add(eid)
        if row["status"] == STATUS_CONFIRMED:
            confirmed_by_year[y].setdefault(eid, []).append(start)

    # Expected from prior year — only within horizon; skip inactive/merged series
    expected_rows: list[dict] = []
    prior_pool = [
        r
        for r in merged
        if r["status"] == STATUS_CONFIRMED
        and isinstance(r.get("start_date"), date)
        and r.get("event_id") not in inactive_ids
    ]
    for y in sorted(expected_years):
        priors = [r for r in prior_pool if r["start_date"].year == y - 1]
        skip_ids = set(skip_by_year.get(y, set())) | inactive_ids
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
                confirmed_by_event=confirmed_by_year.get(y, {}),
                window_days=EXPECTED_WINDOW_DAYS,
            )
            if hit is None:
                kept.append(stub)
        expected_rows.extend(kept)

    all_rows = _dedupe_rows(merged + expected_rows)
    _enrich_geo(
        all_rows,
        locations,
        catalog,
        location_id_by_event=location_id_by_event,
    )

    # Drop nameless rows after catalog enrichment
    named_rows = [r for r in all_rows if _clean_name(r.get("name"))]

    in_window = [r for r in named_rows if r["start_date"].year in years]
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
        "weekend": {"start_weekday": "thu", "end_weekday": "sun"},
        "counts_by_year": {str(y): by_year[str(y)] for y in years_with_data},
        "disclaimer": {
            "en": "Expected (gray) events are projected from the prior year (±1 week per WSDC Registry Rules) for the current calendar year only. They are unconfirmed until published on the WSDC calendar.",
            "ru": "Серые (expected) ивенты — проекция с прошлого года (±1 неделя по правилам WSDC) только для текущего года. Это неподтверждённые даты, пока ивент не появится в календаре WSDC.",
            "es": "Los eventos expected (gris) se proyectan del año anterior (±1 semana según reglas WSDC) solo para el año actual. No están confirmados hasta publicarse en el calendario WSDC.",
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

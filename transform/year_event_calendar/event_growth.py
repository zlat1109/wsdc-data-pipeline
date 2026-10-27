"""Build event_growth.json — YoY competitor growth for the Event Growth Monitor."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from transform.knowledge.geo_flags import continent_for_country
from transform.year_event_calendar.event_cards import (
    _competitions_frame,
    _editions_with_results,
    _estimate_dancers_from_tiers,
    _exact_entries_from_competitions,
    _tiers_frame,
)

# Public map uses four continents (South America folds into America).
PUBLIC_CONTINENTS = frozenset({"America", "Asia", "Australia", "Europe"})

DEFAULT_PCT_THRESHOLD = 0.10
DEFAULT_ABS_THRESHOLD = 10

STATUS_GROWING = "growing"
STATUS_DECLINING = "declining"
STATUS_STABLE = "stable"
STATUS_NEW = "new"
STATUS_RESTARTED = "restarted"

GAP_NONE = None
GAP_ONE_YEAR = "after_1yr_break"
GAP_RESTART = "restarted"


def fold_continent(raw: str | None) -> str | None:
    if not raw:
        return None
    c = str(raw).strip()
    if c == "South America":
        return "America"
    if c in PUBLIC_CONTINENTS:
        return c
    return c or None


def classify_growth(
    current: int | None,
    previous: int | None,
    *,
    year_gap: int | None,
    pct_threshold: float = DEFAULT_PCT_THRESHOLD,
    abs_threshold: int = DEFAULT_ABS_THRESHOLD,
) -> tuple[str, int | None, float | None, str | None]:
    """Return (status, delta, pct, gap_flag).

    year_gap: calendar years between previous edition year and current year
    (current_year - prev_year). None when there is no previous edition.
    - no previous → new
    - year_gap >= 3 (two or more years skipped) → restarted, no %
    - year_gap == 2 (exactly one year skipped) → compare, gap_flag after_1yr_break
    - year_gap == 1 → normal YoY
    """
    if previous is None or current is None:
        return STATUS_NEW, None, None, GAP_NONE

    if year_gap is None:
        return STATUS_NEW, None, None, GAP_NONE

    if year_gap >= 3:
        return STATUS_RESTARTED, None, None, GAP_RESTART

    gap_flag = GAP_ONE_YEAR if year_gap == 2 else GAP_NONE
    delta = int(current) - int(previous)
    if previous == 0:
        pct = None
        status = STATUS_GROWING if delta > 0 else (STATUS_DECLINING if delta < 0 else STATUS_STABLE)
        return status, delta, pct, gap_flag

    pct = delta / float(previous)
    if abs(pct) >= pct_threshold and abs(delta) >= abs_threshold:
        status = STATUS_GROWING if delta > 0 else STATUS_DECLINING
    else:
        status = STATUS_STABLE
    return status, delta, pct, gap_flag


def competitors_for_edition(
    competitions: pd.DataFrame,
    tiers: pd.DataFrame,
    event_id: int,
    year: int,
    month: int,
    unique_dancers_fallback: Any = None,
) -> dict[str, Any] | None:
    """Exact dump Σ(L+F) → tier estimate → unique from editions fallback.

    Returns dict with competitors, approx (0|1), source, or None if no signal.
    """
    exact = _exact_entries_from_competitions(competitions, event_id, year, month)
    if exact is not None:
        return {
            "competitors": int(exact["unique_dancers"]),
            "approx": 0,
            "source": "exact",
            "dancers_min": int(exact["dancers_min"]),
            "dancers_max": int(exact["dancers_max"]),
        }

    estimate = _estimate_dancers_from_tiers(tiers, event_id, year, month)
    if estimate is not None:
        return {
            "competitors": int(estimate["unique_dancers"]),
            "approx": 1,
            "source": "estimated",
            "dancers_min": int(estimate["dancers_min"]),
            "dancers_max": int(estimate["dancers_max"]),
        }

    try:
        ud = (
            int(unique_dancers_fallback)
            if unique_dancers_fallback is not None and not pd.isna(unique_dancers_fallback)
            else None
        )
    except (TypeError, ValueError):
        ud = None
    if ud and ud > 0:
        return {
            "competitors": ud,
            "approx": 0,
            "source": "unique_scored",
            "dancers_min": ud,
            "dancers_max": ud,
        }
    return None


def _clean(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def _location_coords(data_dir: Path) -> dict[int, dict[str, float]]:
    path = data_dir / "location_info.csv"
    if not path.exists():
        return {}
    df = pd.read_csv(path)
    if df.empty or "location_id" not in df.columns:
        return {}
    out: dict[int, dict[str, float]] = {}
    for rec in df.to_dict(orient="records"):
        try:
            lid = int(rec["location_id"])
            lat = float(rec["latitude"])
            lon = float(rec["longitude"])
        except (TypeError, ValueError, KeyError):
            continue
        if abs(lat) > 90 or abs(lon) > 180:
            continue
        out[lid] = {"lat": lat, "lon": lon}
    return out


def _geo_for_row(rec: dict[str, Any], coords: dict[int, dict[str, float]]) -> dict[str, Any]:
    country = _clean(rec.get("place_country"))
    city = _clean(rec.get("place_city"))
    state = _clean(rec.get("place_state"))
    continent = fold_continent(continent_for_country(country) if country else None)
    lat = lon = None
    try:
        lid = int(rec["location_id"]) if rec.get("location_id") not in (None, "") and not pd.isna(rec.get("location_id")) else None
    except (TypeError, ValueError):
        lid = None
    if lid is not None and lid in coords:
        lat = coords[lid]["lat"]
        lon = coords[lid]["lon"]
    return {
        "continent": continent,
        "country": country,
        "state": state,
        "city": city,
        "lat": lat,
        "lon": lon,
    }


def build_event_growth(
    data_dir: Path | str,
    *,
    as_of: date | None = None,
    year_floor: int = 2018,
    pct_threshold: float = DEFAULT_PCT_THRESHOLD,
    abs_threshold: int = DEFAULT_ABS_THRESHOLD,
) -> dict:
    """Build Event Growth Monitor payload."""
    data_dir = Path(data_dir)
    as_of = as_of or date.today()
    editions = _editions_with_results(data_dir)
    competitions = _competitions_frame(data_dir)
    tiers = _tiers_frame(data_dir)
    coords = _location_coords(data_dir)

    as_of_ym = as_of.year * 100 + as_of.month
    rows_out: list[dict[str, Any]] = []

    if editions.empty:
        return _empty_payload(as_of, pct_threshold, abs_threshold, year_floor)

    # Precompute competitor metrics per edition key.
    metrics: dict[tuple[int, int, int], dict[str, Any]] = {}
    edition_meta: dict[tuple[int, int, int], dict[str, Any]] = {}

    for rec in editions.to_dict(orient="records"):
        eid = int(rec["event_id"])
        year = int(rec["event_year"])
        month = int(rec["event_month"])
        ym = year * 100 + month
        if ym > as_of_ym:
            continue
        if year < year_floor:
            # Keep older editions only as previous baselines for later years.
            pass
        key = (eid, year, month)
        if key in metrics:
            continue
        m = competitors_for_edition(
            competitions,
            tiers,
            eid,
            year,
            month,
            unique_dancers_fallback=rec.get("unique_dancers"),
        )
        if m is None:
            continue
        metrics[key] = m
        start = _clean(rec.get("start_date")) or _clean(rec.get("edition_date"))
        edition_meta[key] = {
            "event_id": eid,
            "name": _clean(rec.get("event_name")) or f"Event {eid}",
            "year": year,
            "month": month,
            "start": start,
            **_geo_for_row(rec, coords),
        }

    # Group by event_id sorted by ym.
    by_event: dict[int, list[tuple[int, int, int]]] = {}
    for key in metrics:
        by_event.setdefault(key[0], []).append(key)
    for eid in by_event:
        by_event[eid].sort(key=lambda k: (k[1], k[2]))

    years_seen: set[int] = set()
    for eid, keys in by_event.items():
        for i, key in enumerate(keys):
            year, month = key[1], key[2]
            if year < year_floor:
                continue
            years_seen.add(year)
            meta = edition_meta[key]
            cur = metrics[key]
            prev_key = keys[i - 1] if i > 0 else None
            prev_payload = None
            year_gap = None
            if prev_key is not None:
                prev = metrics[prev_key]
                year_gap = year - prev_key[1]
                prev_payload = {
                    "year": prev_key[1],
                    "month": prev_key[2],
                    "competitors": prev["competitors"],
                    "approx": prev["approx"],
                    "source": prev["source"],
                }

            status, delta, pct, gap_flag = classify_growth(
                cur["competitors"],
                prev_payload["competitors"] if prev_payload else None,
                year_gap=year_gap,
                pct_threshold=pct_threshold,
                abs_threshold=abs_threshold,
            )

            row = {
                **meta,
                "competitors": cur["competitors"],
                "approx": cur["approx"],
                "source": cur["source"],
                "prev": prev_payload,
                "delta": delta,
                "pct": None if pct is None else round(pct, 6),
                "status": status,
                "gap_flag": gap_flag,
            }
            rows_out.append(row)

    rows_out.sort(key=lambda r: (r["year"], r["month"], r["name"], r["event_id"]))
    years = sorted(y for y in years_seen if y >= year_floor)

    data_through = f"{as_of.year:04d}-{as_of.month:02d}"
    if rows_out:
        last = max((r["year"], r["month"]) for r in rows_out)
        data_through = f"{last[0]:04d}-{last[1]:02d}"

    return {
        "as_of": as_of.isoformat(),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_through": data_through,
        "year_floor": year_floor,
        "thresholds": {
            "pct": pct_threshold,
            "abs": abs_threshold,
        },
        "years": years,
        "n_editions": len(rows_out),
        "methodology": {
            "metric": (
                "Competitors = sum of Leader+Follower headcounts over skill levels "
                "Newcomer, Novice, Intermediate, Advanced, All-Star, Champion. "
                "Exact from competitions dump when ≥2 skill divisions have both counts; "
                "otherwise Chart-5 tier midpoint estimate (~); else unique scored dancers."
            ),
            "comparison": (
                "Each edition vs the event's previous scored edition. "
                "One calendar year skipped → compare and mark after_1yr_break. "
                "Two or more years skipped → restarted (no %). No previous → new."
            ),
            "status": (
                f"Growing/Declining when |pct| ≥ {pct_threshold:.0%} and |delta| ≥ {abs_threshold}; "
                "otherwise stable (when comparable)."
            ),
        },
        "editions": rows_out,
    }


def _empty_payload(
    as_of: date, pct_threshold: float, abs_threshold: int, year_floor: int
) -> dict:
    return {
        "as_of": as_of.isoformat(),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_through": f"{as_of.year:04d}-{as_of.month:02d}",
        "year_floor": year_floor,
        "thresholds": {"pct": pct_threshold, "abs": abs_threshold},
        "years": [],
        "n_editions": 0,
        "methodology": {},
        "editions": [],
    }


def write_event_growth(payload: dict, path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def growth_distribution_report(payload: dict, years: list[int] | None = None) -> dict:
    """Phase-0 style summary of statuses / sources / pct distribution."""
    editions = payload.get("editions") or []
    years = years or payload.get("years") or []
    out: dict[str, Any] = {"years": {}}
    for y in years:
        rows = [r for r in editions if r["year"] == y]
        by_status: dict[str, int] = {}
        by_source: dict[str, int] = {}
        comparable_pcts: list[float] = []
        for r in rows:
            by_status[r["status"]] = by_status.get(r["status"], 0) + 1
            src = r.get("source") or ("estimated" if r.get("approx") else "exact")
            by_source[src] = by_source.get(src, 0) + 1
            if r.get("pct") is not None and r["status"] in (
                STATUS_GROWING,
                STATUS_DECLINING,
                STATUS_STABLE,
            ):
                comparable_pcts.append(float(r["pct"]))
        comparable_pcts.sort()

        def pctile(p: float) -> float | None:
            if not comparable_pcts:
                return None
            idx = min(len(comparable_pcts) - 1, max(0, int(round(p * (len(comparable_pcts) - 1)))))
            return round(comparable_pcts[idx], 4)

        out["years"][str(y)] = {
            "n": len(rows),
            "by_status": by_status,
            "by_source": by_source,
            "comparable_n": len(comparable_pcts),
            "pct_p10": pctile(0.10),
            "pct_p25": pctile(0.25),
            "pct_p50": pctile(0.50),
            "pct_p75": pctile(0.75),
            "pct_p90": pctile(0.90),
        }
    out["thresholds"] = payload.get("thresholds")
    return out

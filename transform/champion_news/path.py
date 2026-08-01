"""Champion Path aggregates for a dancer × role timeline."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from transform.champion_news.detect import ResultEvent, _sort_key
from transform.knowledge.geo_flags import continent_for_country


def _event_as_of_date(ev: ResultEvent) -> date:
    return ev.start_date or date(ev.event_year, ev.event_month, 1)


def filter_events_as_of(
    events: list[ResultEvent],
    as_of: date | None,
) -> list[ResultEvent]:
    """Keep only events known on/before as_of (publication / snapshot date)."""
    if as_of is None:
        return list(events)
    return [ev for ev in events if _event_as_of_date(ev) <= as_of]


def build_champion_path(
    events: list[ResultEvent],
    *,
    as_of: date | None = None,
) -> dict:
    """Build expandable path block from point-bearing events for one role.

    If ``as_of`` is set, only editions on/before that date are included so
    archive cards reflect the state at publication time.
    """
    events = filter_events_as_of(events, as_of)
    if not events:
        return {
            "first_points": None,
            "first_all_stars": None,
            "event_counts": {"total": 0, "all_stars": 0, "champions": 0},
            "top_events": [],
            "top_all_stars_events": [],
            "top_cities": [],
            "continents_total": {},
            "continents_all_stars": {},
        }

    ordered = sorted(events, key=_sort_key)

    # Aggregate points per edition for ranking.
    by_edition: dict[tuple[str, int, int], dict] = {}
    for ev in ordered:
        key = (ev.event_name, ev.event_year, ev.event_month)
        bucket = by_edition.setdefault(
            key,
            {
                "event_name": ev.event_name,
                "event_year": ev.event_year,
                "event_month": ev.event_month,
                "points": 0.0,
                "als_points": 0.0,
                "chmp_points": 0.0,
                "location": ev.location_display,
                "country": ev.place_country,
                "start_date": ev.start_date,
            },
        )
        bucket["points"] += ev.event_points
        if ev.division == "ALS":
            bucket["als_points"] += ev.event_points
        elif ev.division == "CHMP":
            bucket["chmp_points"] += ev.event_points
        if ev.start_date and (
            bucket["start_date"] is None or ev.start_date < bucket["start_date"]
        ):
            bucket["start_date"] = ev.start_date
        if ev.location_display and not bucket["location"]:
            bucket["location"] = ev.location_display

    first = ordered[0]
    first_points = {
        "event_name": first.event_name,
        "date": (first.start_date or date(first.event_year, first.event_month, 1)).isoformat(),
        "location": first.location_display,
        "year": first.event_year,
        "month": first.event_month,
    }

    first_als_ev = next((e for e in ordered if e.division == "ALS"), None)
    first_all_stars = None
    if first_als_ev:
        first_all_stars = {
            "event_name": first_als_ev.event_name,
            "date": (
                first_als_ev.start_date
                or date(first_als_ev.event_year, first_als_ev.event_month, 1)
            ).isoformat(),
            "location": first_als_ev.location_display,
            "year": first_als_ev.event_year,
            "month": first_als_ev.event_month,
        }

    editions = list(by_edition.values())
    als_editions = [e for e in editions if e["als_points"] > 0]
    chmp_editions = [e for e in editions if e["chmp_points"] > 0]

    # Top lists are career highlights: sum points across editions of the same series.
    top_events = _top_n_by_series(editions, key="points", n=3)
    top_als = _top_n_by_series(als_editions, key="als_points", n=3)
    top_cities = _rank_cities(ordered, n=3)
    continents_total = _continent_points(editions, points_key="points")
    continents_als = _continent_points(als_editions, points_key="als_points")

    return {
        "first_points": first_points,
        "first_all_stars": first_all_stars,
        "event_counts": {
            "total": len(editions),
            "all_stars": len(als_editions),
            "champions": len(chmp_editions),
        },
        "top_events": top_events,
        "top_all_stars_events": top_als,
        "top_cities": top_cities,
        "continents_total": continents_total,
        "continents_all_stars": continents_als,
    }


def _top_n(items: list[dict], *, key: str, n: int) -> list[dict]:
    ranked = sorted(items, key=lambda x: x.get(key, 0), reverse=True)[:n]
    out = []
    for item in ranked:
        out.append(
            {
                "event_name": item["event_name"],
                "points": int(round(item.get(key, 0))),
                "location": item.get("location") or "",
                "year": item.get("event_year"),
                "month": item.get("event_month"),
            }
        )
    return out


def _top_n_by_series(items: list[dict], *, key: str, n: int) -> list[dict]:
    """Rank event series by summed points across years/editions."""
    series: dict[str, dict] = {}
    for item in items:
        name = (item.get("event_name") or "").strip()
        if not name:
            continue
        bucket_key = name.casefold()
        bucket = series.setdefault(
            bucket_key,
            {
                "event_name": name,
                "points": 0.0,
                "location": item.get("location") or "",
                "event_year": item.get("event_year"),
                "event_month": item.get("event_month"),
            },
        )
        bucket["points"] += float(item.get(key, 0) or 0)
        # Prefer the most recent edition for display year/month/location.
        prev_y = bucket.get("event_year") or 0
        cur_y = item.get("event_year") or 0
        prev_m = bucket.get("event_month") or 0
        cur_m = item.get("event_month") or 0
        if (cur_y, cur_m) >= (prev_y, prev_m):
            bucket["event_year"] = item.get("event_year")
            bucket["event_month"] = item.get("event_month")
            if item.get("location"):
                bucket["location"] = item.get("location")
    ranked = sorted(series.values(), key=lambda x: x["points"], reverse=True)[:n]
    return [
        {
            "event_name": item["event_name"],
            "points": int(round(item["points"])),
            "location": item.get("location") or "",
            "year": item.get("event_year"),
            "month": item.get("event_month"),
        }
        for item in ranked
    ]


def _rank_cities(events: list[ResultEvent], n: int = 3) -> list[dict]:
    city_points: dict[str, float] = defaultdict(float)
    city_label: dict[str, str] = {}
    for ev in events:
        label = ev.location_display or ev.place_city or "Unknown"
        # Normalize ALL CAPS city labels for bucketing.
        key = label.casefold()
        city_points[key] += ev.event_points
        city_label.setdefault(key, label)
    ranked = sorted(city_points.items(), key=lambda kv: kv[1], reverse=True)[:n]
    return [
        {"location": city_label[k], "points": int(round(pts))} for k, pts in ranked
    ]


def _normalize_continent_label(continent: str) -> str:
    """Champion News treats the Americas as one bucket."""
    if continent in {"South America", "North America", "Central America"}:
        return "America"
    return continent


def _continent_points(editions: list[dict], *, points_key: str) -> dict[str, int]:
    totals: dict[str, float] = defaultdict(float)
    for ed in editions:
        country = ed.get("country") or ""
        continent = continent_for_country(country) if country else "Unknown"
        if not continent:
            continent = "Unknown"
        continent = _normalize_continent_label(continent)
        totals[continent] += ed.get(points_key, 0) or 0
    # Highest points first; tie-break by continent name.
    ranked = sorted(
        ((c, pts) for c, pts in totals.items() if pts > 0),
        key=lambda item: (-item[1], item[0]),
    )
    return {c: int(round(pts)) for c, pts in ranked}

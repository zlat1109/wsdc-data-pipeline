"""Normalize scraped WSDC Events List rows."""

from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Any
from urllib.parse import urlparse

from parser.events_list_dates import edition_month_candidates
from transform.events_list_maps import clean_list_location, country_from_location

_COUNTRY_ALPHA3: dict[str, str] = {
    "USA": "United States",
    "GBR": "United Kingdom",
    "CAN": "Canada",
    "AUS": "Australia",
    "DEU": "Germany",
    "FRA": "France",
    "ESP": "Spain",
    "ITA": "Italy",
    "SWE": "Sweden",
    "NOR": "Norway",
    "DNK": "Denmark",
    "FIN": "Finland",
    "NLD": "Netherlands",
    "BEL": "Belgium",
    "AUT": "Austria",
    "CHE": "Switzerland",
    "POL": "Poland",
    "CZE": "Czech Republic",
    "HUN": "Hungary",
    "RUS": "Russia",
    "UKR": "Ukraine",
    "JPN": "Japan",
    "KOR": "Republic of Korea",
    "SGP": "Singapore",
    "NZL": "New Zealand",
    "BRA": "Brazil",
    "MEX": "Mexico",
    "IRL": "Ireland",
    "PRT": "Portugal",
    "SVK": "Slovakia",
    "SVN": "Slovenia",
    "BGR": "Bulgaria",
    "ROU": "Romania",
    "LVA": "Latvia",
    "MYS": "Malaysia",
}

_UNCONFIRMED_RE = re.compile(
    r"\(unconfirmed\)|\(unconirmed\)|\(unfonfirmed\)| unconfirmed\)",
    re.I,
)
_HIATUS_NAME_RE = re.compile(r"\(on hiatus\)|\(hiatus\)", re.I)

REGISTRY_STATUS = "Registry Event"
TRIAL_STATUS = "Trial Event"
VALID_STATUS_EVENTS = frozenset({REGISTRY_STATUS, TRIAL_STATUS})


def normalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url.strip().lower())
    netloc = parsed.netloc
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parsed.path.rstrip("/")
    if not netloc:
        return ""
    return f"{netloc}{path}"


def source_fingerprint(event_name: str, start_date: str, url: str) -> str:
    norm_url = normalize_url(url)
    if norm_url:
        raw = f"{norm_url}|{start_date}"
    else:
        raw = f"{event_name.strip().lower()}|{start_date}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def canonical_status_event(*sources: str) -> str:
    """Map scrape/name text to WSDC schedule status (always Registry or Trial)."""
    for source in sources:
        if not source:
            continue
        low = source.lower()
        if "trial event" in low or low.strip() == "trial":
            return TRIAL_STATUS
        if "registry event" in low or low.strip() == "registry":
            return REGISTRY_STATUS
    return REGISTRY_STATUS


def clean_event_name(raw_name: str, event_type_raw: str = "") -> tuple[str, str, bool, bool]:
    """Return (name, status_event, confirmed, on_hiatus)."""
    name = raw_name.strip()
    on_hiatus = bool(_HIATUS_NAME_RE.search(name))
    name = _HIATUS_NAME_RE.sub("", name).strip()

    status_event = (event_type_raw or "").strip()
    if not status_event:
        if "Registry Event" in name:
            status_event = REGISTRY_STATUS
            name = name.replace("Registry Event", "").strip()
        elif "Trial Event" in name or "(Trial Event)" in name:
            status_event = TRIAL_STATUS
            name = name.replace("(Trial Event)", "").replace("Trial Event", "").strip()

    status_event = canonical_status_event(status_event, raw_name)

    confirmed = True
    if _UNCONFIRMED_RE.search(name):
        confirmed = False
        name = _UNCONFIRMED_RE.sub("", name).strip()

    return name.strip(" -"), status_event, confirmed, on_hiatus


def flag_to_country(flag: str) -> str:
    if not flag:
        return ""
    return _COUNTRY_ALPHA3.get(flag.upper(), "")


def country_to_flag(country: str) -> str:
    if not country:
        return ""
    for code, name in _COUNTRY_ALPHA3.items():
        if name == country:
            return code
    return ""


_PLACEHOLDER_FLAGS = frozenset({"TRANSPARENT"})


def _clean_scraped_flag(country_flag: str) -> str:
    flag = (country_flag or "").strip().upper()
    if flag in _PLACEHOLDER_FLAGS:
        return ""
    return flag


def resolve_country_fields(country_flag: str, location_raw: str) -> tuple[str, str]:
    """Return (country, country_flag); derive missing side from flag or location text."""
    flag = _clean_scraped_flag(country_flag)
    country = flag_to_country(flag) if flag else ""

    if not country:
        country = country_from_location(location_raw)
    if country and not flag:
        flag = country_to_flag(country)
    if flag and not country:
        country = flag_to_country(flag)

    return country, flag


def normalize_event(raw: dict[str, Any]) -> dict[str, Any]:
    name, status_event, confirmed, hiatus_from_name = clean_event_name(
        raw.get("event_name") or "",
        raw.get("event_type_raw") or "",
    )
    start = date.fromisoformat(raw["start_date"])
    end = date.fromisoformat(raw["end_date"])
    edition = edition_month_candidates(start, end)
    results_year, results_month = edition[0] if edition else (end.year, end.month)

    scraped_location = raw.get("location_raw") or ""
    location_raw = clean_list_location(scraped_location)

    country, country_flag = resolve_country_fields(raw.get("country_flag") or "", location_raw)

    fp = source_fingerprint(name, raw["start_date"], raw.get("url") or "")

    return {
        "source_fingerprint": fp,
        "event_name": name,
        "original_date": raw.get("original_date") or "",
        "start_date": raw["start_date"],
        "end_date": raw["end_date"],
        "results_year": results_year,
        "results_month": results_month,
        "location_raw": location_raw,
        "location_raw_original": scraped_location,
        "country": country,
        "country_flag": country_flag,
        "url": raw.get("url") or "",
        "status_event": status_event,
        "confirmed": confirmed,
        "canceled": bool(raw.get("canceled")),
        "on_hiatus": bool(raw.get("on_hiatus")) or hiatus_from_name,
        "is_active": not (bool(raw.get("canceled")) or bool(raw.get("on_hiatus")) or hiatus_from_name),
    }


def normalize_events(raw_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = [normalize_event(e) for e in raw_events]
    return _dedupe_scheduled_rows(normalized)


def _url_rank(url: str) -> int:
    norm = normalize_url(url)
    return len(norm)


def _dedupe_scheduled_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop duplicate name+date rows; prefer row with a real event URL."""
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for ev in events:
        key = (ev["event_name"].strip().lower(), ev["start_date"])
        prev = best.get(key)
        if prev is None or _url_rank(ev.get("url") or "") > _url_rank(prev.get("url") or ""):
            best[key] = ev
    return list(best.values())

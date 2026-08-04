"""Normalize WSDC FullCalendar event rows into edition-ready dates."""

from __future__ import annotations

import hashlib
import re
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlparse

from parser.events_list_dates import edition_month_candidates
from transform.events_list_normalize import normalize_url
from transform.knowledge.event_aliases import (
    EVENT_NAME_VARIANT_TO_CATALOG,
    RESULT_TO_CATALOG_EVENT_NAME,
)

_PAREN_STATUS_RE = re.compile(
    r"\(([^)]*(?:hiatus|cancelled|canceled|trial|unconfirmed|unconirmed|unfonfirmed|"
    r"postponed|tentative)[^)]*)\)",
    re.I,
)
_YEAR_SUFFIX_RE = re.compile(r"\s+20\d{2}\s*$")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

# Max inclusive span for a real weekend event (reject sentinel / bad ends).
_MAX_INCLUSIVE_DAYS = 21


def _parse_iso_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.startswith("-"):
        return None
    # FullCalendar may emit datetime; take date part.
    text = text[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def strip_status_parens(title: str) -> tuple[str, list[str]]:
    """Remove status parentheticals from title; return clean name + tags."""
    tags: list[str] = []
    name = str(title or "").strip()

    def _collect(match: re.Match[str]) -> str:
        tags.append(match.group(1).strip().lower())
        return " "

    name = _PAREN_STATUS_RE.sub(_collect, name)
    name = re.sub(r"\s+", " ", name).strip()
    return name, tags


def strip_all_parens(title: str) -> str:
    """Drop any parenthetical segment (aliases, abbreviations)."""
    name = re.sub(r"\([^)]*\)", " ", str(title or ""))
    return re.sub(r"\s+", " ", name).strip()


def catalog_name_from_calendar_title(title: str) -> str:
    """Map calendar title toward core.events / catalog naming."""
    name, _ = strip_status_parens(title)
    name = _YEAR_SUFFIX_RE.sub("", name).strip()
    # Try full string, then without any parentheses.
    candidates = [name, strip_all_parens(name)]
    # Leading token before paren: "MADjam (Mid Atlantic...)" → MADjam
    lead = re.match(r"^([^(]+)", name)
    if lead:
        candidates.append(lead.group(1).strip())
    low_maps = {
        **{k.lower(): v for k, v in RESULT_TO_CATALOG_EVENT_NAME.items()},
        **{k.lower(): v for k, v in EVENT_NAME_VARIANT_TO_CATALOG.items()},
        "capital swing convention": "Capital Swing Dance Convention",
        "madjam mid-atlantic dance jam": "Mid-Atlantic Dance Jam",
        "madjam mid atlantic dance jam": "Mid-Atlantic Dance Jam",
    }
    for cand in candidates:
        if not cand:
            continue
        mapped = low_maps.get(cand.lower())
        if mapped:
            return mapped
    return strip_all_parens(name) or name


def name_key(name: str) -> str:
    return _NON_ALNUM_RE.sub("", catalog_name_from_calendar_title(name).lower())


def inclusive_end_from_fullcalendar(start: date, end: date | None) -> date | None:
    """FullCalendar all-day `end` is exclusive → last inclusive day is end-1."""
    if end is None:
        return start
    if end <= start:
        return None
    inclusive = end - timedelta(days=1)
    if inclusive < start:
        return None
    return inclusive


def source_fingerprint(event_name: str, start_date: str, url: str) -> str:
    norm_url = normalize_url(url)
    if norm_url:
        raw = f"{norm_url}|{start_date}"
    else:
        raw = f"{event_name.strip().lower()}|{start_date}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def normalize_calendar_event(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Convert one FullCalendar row to a normalized calendar event dict."""
    title = str(raw.get("title") or "").strip()
    if not title:
        return None

    start = _parse_iso_date(raw.get("start"))
    if start is None:
        return None

    raw_end = _parse_iso_date(raw.get("end"))
    end = inclusive_end_from_fullcalendar(start, raw_end)
    clean_name, status_tags = strip_status_parens(title)
    clean_name = _YEAR_SUFFIX_RE.sub("", clean_name).strip() or clean_name

    flags: list[str] = []
    if end is None and raw_end is not None:
        flags.append("invalid_end")
    if end is not None and (end - start).days > _MAX_INCLUSIVE_DAYS:
        flags.append("span_too_long")
        end = None
    if any("hiatus" in t for t in status_tags):
        flags.append("hiatus")
    if any("cancel" in t for t in status_tags):
        flags.append("cancelled")
    if any("trial" in t for t in status_tags):
        flags.append("trial")
    if any("unconfirm" in t or "unconirm" in t or "unfonfirm" in t for t in status_tags):
        flags.append("unconfirmed")

    url = str(raw.get("url") or "").strip()
    catalog_name = catalog_name_from_calendar_title(title)
    start_s = start.isoformat()
    end_s = end.isoformat() if end else ""
    yms = edition_month_candidates(start, end or start)

    return {
        "event_name": clean_name,
        "calendar_title": title,
        "catalog_name": catalog_name,
        "name_key": name_key(title),
        "start_date": start_s,
        "end_date": end_s,
        "url": url,
        "url_key": normalize_url(url),
        "results_year": yms[0][0] if yms else start.year,
        "results_month": yms[0][1] if yms else start.month,
        "edition_ym_candidates": [f"{y}-{m:02d}" for y, m in yms],
        "date_precision": "day" if end else "day_start_only",
        "date_source": "wsdc_calendar",
        "flags": flags,
        "status_tags": status_tags,
        "source_fingerprint": source_fingerprint(clean_name, start_s, url),
        "raw_start": str(raw.get("start") or ""),
        "raw_end": str(raw.get("end") or ""),
    }


def normalize_calendar_events(
    raw_events: list[dict[str, Any]],
    *,
    min_start: date | None = date(2025, 1, 1),
) -> list[dict[str, Any]]:
    """Normalize and optionally filter by date window.

    Includes cross-year weekends that start before ``min_start`` but overlap it.
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_events:
        row = normalize_calendar_event(raw)
        if row is None:
            continue
        start = date.fromisoformat(row["start_date"])
        end = date.fromisoformat(row["end_date"]) if row.get("end_date") else start
        if min_start is not None and end < min_start:
            continue
        fp = row["source_fingerprint"]
        if fp in seen:
            continue
        seen.add(fp)
        out.append(row)
    out.sort(key=lambda r: (r["start_date"], r["event_name"].lower()))
    return out


def host_key(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url.strip().lower())
    netloc = parsed.netloc
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc

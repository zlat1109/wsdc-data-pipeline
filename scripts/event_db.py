"""Check whether a WSDC event edition is already loaded in core.results."""

from __future__ import annotations

import os
import json
import re
from datetime import date, datetime, timedelta
from typing import Any
from pathlib import Path

from parser.event_name_matcher import find_best_match

ISO_DATE = "%Y-%m-%d"
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Suggestions captured during split_pending_events; consumed by check_updates report.
_DB_SUGGESTIONS: dict[str, dict[str, Any]] = {}


def reset_db_suggestions() -> None:
    _DB_SUGGESTIONS.clear()


def get_db_suggestions() -> dict[str, dict[str, Any]]:
    return dict(_DB_SUGGESTIONS)


def _forced_gate_event_names() -> set[str]:
    """Events treated as gate-relevant even before standard concluded checks.

    Use for known lagging score publications where we still want check-updates
    to keep showing the event as pending this week.
    """
    raw = os.getenv("EVENT_GATE_FORCE_PENDING_NAMES", "")
    return {name.strip() for name in raw.split(",") if name.strip()}


_YEAR_SUFFIX_RE = re.compile(r"\s+(20\d{2})\s*$")


def _strip_year_suffix(name: str) -> str:
    return _YEAR_SUFFIX_RE.sub("", name).strip()


def _load_event_aliases_json() -> dict[str, str]:
    """Load alias→canonical map exported to data/event_aliases.json (if present)."""
    path = PROJECT_ROOT / "data" / "event_aliases.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    mappings = payload.get("mappings")
    return mappings if isinstance(mappings, dict) else {}


def normalize_expected_event_name(raw: str, *, aliases: dict[str, str] | None = None) -> str:
    """Normalize snapshot/schedule event names into catalog-ish names for matching."""
    name = (raw or "").strip()
    if not name:
        return ""
    aliases = aliases if aliases is not None else _load_event_aliases_json()
    if name in aliases:
        name = str(aliases[name]).strip()
    # Common snapshot pattern: "Event Name 2026"
    name = _strip_year_suffix(name)
    if name in aliases:
        name = str(aliases[name]).strip()
    return name


def _parse_iso_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], ISO_DATE).date()
    except ValueError:
        return None


def event_results_edition(event: dict[str, Any]) -> tuple[int | None, int | None]:
    """WSDC results edition year/month from snapshot row (explicit or start_date)."""
    year = event.get("results_year")
    month = event.get("results_month")
    if year is not None and month is not None:
        try:
            return int(year), int(month)
        except (TypeError, ValueError):
            pass
    start = _parse_iso_date(event.get("start_date"))
    if start is not None:
        return start.year, start.month
    return None, None


def event_has_concluded(event: dict[str, Any], today: date | None = None) -> bool:
    """True when the event weekend is over (results may exist on WSDC).

    On Mon–Fri probes, an event whose ``end_date`` is today counts as concluded
    (e.g. Jul 2–6 events on Monday Jul 6). On Sat/Sun the last calendar day is
    still treated as ongoing so weekend-day probes do not expect results early.
    """
    today = today or date.today()
    end = _parse_iso_date(event.get("end_date"))
    start = _parse_iso_date(event.get("start_date"))
    last_day = end or start
    if last_day is None:
        return True
    if last_day < today:
        return True
    # Weekday probe on the event's last day (Mon=0 .. Fri=4).
    return last_day == today and today.weekday() < 5


def fetch_event_names_for_edition(conn, year: int, month: int) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT e.name
            FROM core.results r
            JOIN core.events e ON e.event_id = r.event_id
            WHERE r.event_year = %s AND r.event_month = %s
            """,
            (year, month),
        )
        return [row[0] for row in cur.fetchall() if row[0]]


def _match_names_for_edition(
    raw_name: str,
    db_names: list[str],
    *,
    aliases: dict[str, str],
    threshold: float,
) -> tuple[str | None, float]:
    """Try raw snapshot name first (EVENT_NAME_MAPPINGS), then JSON-normalized."""
    candidates: list[str] = []
    seen: set[str] = set()
    for candidate in (
        (raw_name or "").strip(),
        normalize_expected_event_name(raw_name, aliases=aliases),
    ):
        if candidate and candidate not in seen:
            seen.add(candidate)
            candidates.append(candidate)
    best_match: str | None = None
    best_score = 0.0
    for candidate in candidates:
        match, score = find_best_match(candidate, db_names, threshold=threshold)
        if match and score > best_score:
            best_match = match
            best_score = score
    return best_match, best_score


def event_edition_in_db(
    conn,
    event_name: str,
    year: int | None,
    month: int | None,
    *,
    threshold: float = 0.75,
) -> bool:
    if year is None or month is None:
        return False
    raw_name = (event_name or "").strip()
    if not raw_name:
        return False
    aliases = _load_event_aliases_json()
    db_names = fetch_event_names_for_edition(conn, year, month)
    if not db_names:
        return False
    match, _ = _match_names_for_edition(
        raw_name, db_names, aliases=aliases, threshold=threshold
    )
    return match is not None


def suggest_db_match(
    conn,
    event_name: str,
    year: int | None,
    month: int | None,
    *,
    threshold: float = 0.60,
) -> tuple[str | None, float]:
    """Return best candidate name in DB for this edition (even when below gate threshold)."""
    if year is None or month is None:
        return None, 0.0
    raw_name = (event_name or "").strip()
    if not raw_name:
        return None, 0.0
    aliases = _load_event_aliases_json()
    db_names = fetch_event_names_for_edition(conn, year, month)
    if not db_names:
        return None, 0.0
    return _match_names_for_edition(
        raw_name, db_names, aliases=aliases, threshold=threshold
    )


def event_last_day(event: dict[str, Any]) -> date | None:
    """Last calendar day of the event (end_date, else start_date)."""
    end = _parse_iso_date(event.get("end_date"))
    start = _parse_iso_date(event.get("start_date"))
    return end or start


def events_within_gate_lookback(
    events: list[dict[str, Any]],
    *,
    today: date | None = None,
    lookback_days: int | None = None,
) -> list[dict[str, Any]]:
    """Keep concluded events whose last day is within the gate lookback window."""
    today = today or date.today()
    lookback_days = lookback_days or int(os.getenv("EVENT_GATE_LOOKBACK_DAYS", "21"))
    cutoff = today - timedelta(days=lookback_days)
    relevant: list[dict[str, Any]] = []
    forced_names = _forced_gate_event_names()
    for event in events:
        name = (event.get("name") or "").strip()
        forced = name in forced_names
        if not forced and not event_has_concluded(event, today):
            continue
        last_day = event_last_day(event)
        if last_day is None or last_day >= cutoff:
            relevant.append(event)
    return relevant


def split_pending_events(
    conn,
    events: list[dict[str, Any]],
    *,
    threshold: float = 0.75,
    today: date | None = None,
) -> tuple[list[str], list[str]]:
    """Return (pending_names, already_in_db_names) for concluded snapshot events."""
    today = today or date.today()
    aliases = _load_event_aliases_json()
    pending: list[str] = []
    already: list[str] = []
    forced_names = _forced_gate_event_names()
    for event in events:
        name = (event.get("name") or "").strip()
        if not name:
            continue
        forced = name in forced_names
        if not forced and not event_has_concluded(event, today):
            continue
        year, month = event_results_edition(event)
        normalized = normalize_expected_event_name(name, aliases=aliases)
        if event_edition_in_db(conn, name, year, month, threshold=threshold):
            already.append(name)
        else:
            pending.append(name)
            if name not in _DB_SUGGESTIONS:
                suggestion, score = suggest_db_match(conn, name, year, month, threshold=0.60)
                if suggestion:
                    _DB_SUGGESTIONS[name] = {
                        "normalized": normalized,
                        "suggested_db_name": suggestion,
                        "score": round(float(score), 3),
                        "edition_year": year,
                        "edition_month": month,
                    }
    return pending, already

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


_SCHEDULED_RESULTS_INDEX: dict[str, list[dict[str, Any]]] | None = None


def _load_scheduled_results_index() -> dict[str, list[dict[str, Any]]]:
    """Map normalized event name → scheduled edition rows with results_year/month."""
    global _SCHEDULED_RESULTS_INDEX
    if _SCHEDULED_RESULTS_INDEX is not None:
        return _SCHEDULED_RESULTS_INDEX
    path = PROJECT_ROOT / "data" / "scheduled_events.csv"
    index: dict[str, list[dict[str, Any]]] = {}
    if not path.exists():
        _SCHEDULED_RESULTS_INDEX = index
        return index
    try:
        import csv

        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                name = (row.get("canonical_name") or row.get("event_name") or "").strip()
                if not name:
                    continue
                try:
                    year = int(row["results_year"])
                    month = int(row["results_month"])
                except (KeyError, TypeError, ValueError):
                    continue
                key = normalize_expected_event_name(name).lower()
                if not key:
                    continue
                index.setdefault(key, []).append(
                    {
                        "results_year": year,
                        "results_month": month,
                        "start_date": _parse_iso_date(row.get("start_date")),
                        "end_date": _parse_iso_date(row.get("end_date")),
                    }
                )
    except OSError:
        index = {}
    _SCHEDULED_RESULTS_INDEX = index
    return index


def _lookup_scheduled_results_edition(event: dict[str, Any]) -> tuple[int | None, int | None]:
    """Prefer results edition from scheduled_events when snapshot omits results_*."""
    raw_name = (event.get("name") or "").strip()
    if not raw_name:
        return None, None
    aliases = _load_event_aliases_json()
    keys = {
        normalize_expected_event_name(raw_name, aliases=aliases).lower(),
        raw_name.lower(),
    }
    start = _parse_iso_date(event.get("start_date"))
    end = _parse_iso_date(event.get("end_date"))
    index = _load_scheduled_results_index()
    candidates: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for key in keys:
        if not key:
            continue
        for row in index.get(key, []):
            row_id = id(row)
            if row_id in seen_ids:
                continue
            seen_ids.add(row_id)
            candidates.append(row)
    if not candidates:
        return None, None

    scored: list[tuple[int, dict[str, Any]]] = []
    for row in candidates:
        row_start = row.get("start_date")
        row_end = row.get("end_date")
        if start is not None and row_start is not None:
            delta = abs((start - row_start).days)
            if delta <= 14:
                scored.append((delta, row))
                continue
        # Date-range overlap for cross-month / slight drift.
        if start is not None and end is not None and row_start is not None and row_end is not None:
            if start <= row_end and end >= row_start:
                scored.append((abs((start - row_start).days), row))

    if not scored:
        return None, None
    scored.sort(key=lambda item: item[0])
    row = scored[0][1]
    return int(row["results_year"]), int(row["results_month"])


def event_results_edition(event: dict[str, Any]) -> tuple[int | None, int | None]:
    """WSDC results edition year/month for gate lookups.

    Preference:
    1. Explicit snapshot ``results_year`` / ``results_month``
    2. Matching row in ``data/scheduled_events.csv``
    3. ``end_date`` month when the event spans months (WSDC editions follow end month)
    4. ``start_date`` month
    """
    year = event.get("results_year")
    month = event.get("results_month")
    if year is not None and month is not None:
        try:
            return int(year), int(month)
        except (TypeError, ValueError):
            pass

    scheduled = _lookup_scheduled_results_edition(event)
    if scheduled[0] is not None and scheduled[1] is not None:
        return scheduled

    start = _parse_iso_date(event.get("start_date"))
    end = _parse_iso_date(event.get("end_date"))
    if start is not None and end is not None and (end.year, end.month) != (start.year, start.month):
        return end.year, end.month
    if start is not None:
        return start.year, start.month
    if end is not None:
        return end.year, end.month
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


def _year_split_family_names(name: str) -> list[str]:
    """Early/late titles that share one WSDC id across a rebrand year.

    Weekend gate joins ``core.events.name``; that row stays one brand (often the
    old one until enrich runs). Snapshot calendars use the current brand, so
    fuzzy match alone fails (UpTown ↔ Swedish score 0). Treat the family as
    interchangeable for edition presence checks.
    """
    from transform.knowledge.event_aliases import EVENT_NAME_YEAR_SPLITS

    needle = (name or "").strip()
    if not needle:
        return []
    needle_l = needle.lower()
    out: list[str] = []
    for rule in EVENT_NAME_YEAR_SPLITS:
        sources = {str(s).strip() for s in rule["sources"]}  # type: ignore[arg-type]
        early = str(rule["early_name"]).strip()
        late = str(rule["late_name"]).strip()
        family = {n for n in (sources | {early, late}) if n}
        if not any(needle_l == n.lower() for n in family):
            continue
        for n in (early, late, *sorted(sources)):
            if n and n not in out:
                out.append(n)
    return out


def _match_names_for_edition(
    raw_name: str,
    db_names: list[str],
    *,
    aliases: dict[str, str],
    threshold: float,
) -> tuple[str | None, float]:
    """Try raw snapshot name first (EVENT_NAME_MAPPINGS), then JSON-normalized.

    Also tries year-split sibling titles (Swedish↔UpTown, BTO↔Calgary, …).
    """
    candidates: list[str] = []
    seen: set[str] = set()
    seed = (
        (raw_name or "").strip(),
        normalize_expected_event_name(raw_name, aliases=aliases),
    )
    for candidate in seed:
        if candidate and candidate not in seen:
            seen.add(candidate)
            candidates.append(candidate)
        for sibling in _year_split_family_names(candidate):
            if sibling not in seen:
                seen.add(sibling)
                candidates.append(sibling)
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

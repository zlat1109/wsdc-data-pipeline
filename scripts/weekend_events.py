"""Load upcoming-weekend snapshots (from telegram-news-bot weekly bot)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

ISO_DATE = "%Y-%m-%d"
FILENAME_TEMPLATE = "weekend_{start}_{end}.json"


@dataclass(frozen=True)
class WeekendSnapshot:
    weekend_start: date
    weekend_end: date
    events: list[dict[str, Any]]
    source_path: Path
    generated_at: datetime | None = None


def weekend_events_dir() -> Path:
    override = os.getenv("WEEKEND_EVENTS_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1] / "data" / "weekend_events"


def get_current_weekend_dates(today: date | None = None) -> tuple[date, date]:
    """Mon–Sun bucket for the current upcoming weekend (same logic as weekly bot)."""
    today = today or date.today()
    weekday = today.weekday()

    if weekday == 5:
        saturday = today
        sunday = saturday + timedelta(days=1)
    elif weekday == 6:
        saturday = today - timedelta(days=1)
        sunday = today
    else:
        days_until_saturday = (5 - weekday) % 7
        if days_until_saturday == 0:
            days_until_saturday = 7
        saturday = today + timedelta(days=days_until_saturday)
        sunday = saturday + timedelta(days=1)

    friday = saturday - timedelta(days=1)
    monday = sunday + timedelta(days=1)
    weekend_start = friday - timedelta(days=friday.weekday())
    weekend_end = monday + timedelta(days=6 - monday.weekday())
    return weekend_start, weekend_end


def _load_snapshot(path: Path) -> WeekendSnapshot:
    data = json.loads(path.read_text(encoding="utf-8"))
    generated_at = None
    if raw := data.get("generated_at"):
        generated_at = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ")
    return WeekendSnapshot(
        weekend_start=datetime.strptime(data["weekend_start"], ISO_DATE).date(),
        weekend_end=datetime.strptime(data["weekend_end"], ISO_DATE).date(),
        events=data.get("events", []),
        source_path=path,
        generated_at=generated_at,
    )


def list_snapshots() -> list[WeekendSnapshot]:
    data_dir = weekend_events_dir()
    snapshots: list[WeekendSnapshot] = []
    seen: set[Path] = set()

    for path in sorted(data_dir.glob("weekend_*.json")):
        if path in seen:
            continue
        try:
            snapshots.append(_load_snapshot(path))
            seen.add(path)
        except (json.JSONDecodeError, KeyError, ValueError):
            continue

    latest = data_dir / "latest.json"
    if latest.exists() and latest not in seen:
        try:
            snapshots.append(_load_snapshot(latest))
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

    snapshots.sort(
        key=lambda s: (
            s.generated_at or datetime.min,
            s.weekend_start,
        ),
        reverse=True,
    )
    return snapshots


def load_latest_snapshot() -> WeekendSnapshot | None:
    latest = weekend_events_dir() / "latest.json"
    if not latest.exists():
        return None
    try:
        return _load_snapshot(latest)
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def load_weekend_events(week_start: date, week_end: date) -> WeekendSnapshot | None:
    data_dir = weekend_events_dir()
    expected = data_dir / FILENAME_TEMPLATE.format(
        start=week_start.strftime(ISO_DATE),
        end=week_end.strftime(ISO_DATE),
    )
    if expected.exists():
        return _load_snapshot(expected)

    best: WeekendSnapshot | None = None
    best_overlap = 0
    for path in sorted(data_dir.glob("weekend_*.json")):
        try:
            snap = _load_snapshot(path)
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
        if snap.weekend_start <= week_end and snap.weekend_end >= week_start:
            overlap_start = max(snap.weekend_start, week_start)
            overlap_end = min(snap.weekend_end, week_end)
            overlap = (overlap_end - overlap_start).days + 1
            if overlap > best_overlap:
                best = snap
                best_overlap = overlap

    if best:
        return best

    latest = data_dir / "latest.json"
    if latest.exists():
        snap = _load_snapshot(latest)
        if snap.weekend_start <= week_end and snap.weekend_end >= week_start:
            return snap
    return None


def resolve_pending_snapshot(
    conn,
    *,
    today: date | None = None,
) -> tuple[WeekendSnapshot | None, list[str], list[str]]:
    """Pick snapshot and pending events for concluded weekends not yet in DB."""
    snap, pending, already, status = resolve_event_gate(conn, today=today)
    if status != "pending":
        return None, [], []
    return snap, pending, already


def _pick_primary_snapshot(
    views: list[tuple[WeekendSnapshot, list[str], list[str]]],
    *,
    require_pending: bool,
) -> WeekendSnapshot:
    """Prefer the snapshot for the most recent weekend window with work left."""
    candidates = [item for item in views if item[1]] if require_pending else views
    snap, _, _ = max(
        candidates,
        key=lambda item: (
            item[0].weekend_end,
            item[0].generated_at or datetime.min,
            item[0].weekend_start,
        ),
    )
    return snap


def resolve_event_gate(
    conn,
    *,
    today: date | None = None,
) -> tuple[WeekendSnapshot | None, list[str], list[str], str]:
    """Resolve weekend event gate for check-updates.

    Merges pending/already lists across **all** snapshots so a carry-over event
    from last week (e.g. delayed Neverland) stays in the gate together with this
    week's concluded events. A newer ``generated_at`` on an older weekend window
    must not hide pending events from a later weekend.

    Returns (snapshot, pending, already_in_db, status):
    - ``no_concluded_events`` — quiet / future-only weekend in snapshots
    - ``all_loaded`` — every concluded event in every snapshot is in Supabase
    - ``pending`` — at least one concluded event is still missing from Supabase
    """
    from event_db import events_within_gate_lookback, split_pending_events, reset_db_suggestions

    today = today or date.today()
    threshold = float(os.getenv("EVENT_COVERAGE_THRESHOLD", "0.75"))
    views: list[tuple[WeekendSnapshot, list[str], list[str]]] = []
    merged_pending: list[str] = []
    pending_names: set[str] = set()
    merged_already: list[str] = []
    already_names: set[str] = set()

    reset_db_suggestions()
    for snap in list_snapshots():
        relevant_events = events_within_gate_lookback(snap.events, today=today)
        pending, already = split_pending_events(
            conn, relevant_events, threshold=threshold, today=today
        )
        if not pending and not already:
            continue
        views.append((snap, pending, already))
        for name in pending:
            if name in pending_names:
                continue
            pending_names.add(name)
            merged_pending.append(name)
            if name in already_names:
                already_names.remove(name)
                merged_already = [n for n in merged_already if n != name]
        for name in already:
            if name in pending_names or name in already_names:
                continue
            already_names.add(name)
            merged_already.append(name)

    if not views:
        return None, [], [], "no_concluded_events"
    if merged_pending:
        primary = _pick_primary_snapshot(views, require_pending=True)
        return primary, merged_pending, merged_already, "pending"
    primary = _pick_primary_snapshot(views, require_pending=False)
    return primary, [], merged_already, "all_loaded"


def expected_event_names(snapshot: WeekendSnapshot) -> list[str]:
    names: list[str] = []
    for event in snapshot.events:
        name = (event.get("name") or "").strip()
        if name:
            names.append(name)
    return names

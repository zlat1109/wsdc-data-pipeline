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
    """Pick snapshot with concluded events not yet in DB; prefer newest generated_at."""
    from event_db import split_pending_events

    today = today or date.today()
    threshold = float(os.getenv("EVENT_COVERAGE_THRESHOLD", "0.75"))
    best: WeekendSnapshot | None = None
    best_pending: list[str] = []
    best_already: list[str] = []

    for snap in list_snapshots():
        pending, already = split_pending_events(
            conn, snap.events, threshold=threshold, today=today
        )
        if not pending:
            continue
        if best is None or (
            (snap.generated_at or datetime.min, snap.weekend_start)
            > (best.generated_at or datetime.min, best.weekend_start)
        ):
            best = snap
            best_pending = pending
            best_already = already

    return best, best_pending, best_already


def expected_event_names(snapshot: WeekendSnapshot) -> list[str]:
    names: list[str] = []
    for event in snapshot.events:
        name = (event.get("name") or "").strip()
        if name:
            names.append(name)
    return names

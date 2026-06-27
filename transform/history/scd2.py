"""Shared SCD2 interval helpers for points and roles history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterator


@dataclass(frozen=True)
class HistoryKey:
    dancer_id: int
    role: str
    dance: str
    level: str


@dataclass
class HistoryInterval:
    key: HistoryKey
    total_points: int | None = None
    valid_from: date | None = None
    valid_to: date | None = None


def close_interval(valid_to: date) -> date:
    """Last valid day of a closed interval before next valid_from."""
    return valid_to


def next_valid_to(next_valid_from: date) -> date:
    return next_valid_from - timedelta(days=1)


def iter_point_changes(
    rows: list[dict],
) -> Iterator[tuple[HistoryKey, int, date]]:
    """Yield (key, total_points, snap_date) for rows where points changed per key."""
    grouped: dict[HistoryKey, list[tuple[date, int]]] = {}
    for row in rows:
        key = HistoryKey(
            int(row["dancer_id"]),
            str(row["role"]),
            str(row["dance"]),
            str(row["level"]),
        )
        snap = row["snap_date"]
        if isinstance(snap, str):
            snap = date.fromisoformat(snap[:10])
        pts = int(row["total_points"])
        grouped.setdefault(key, []).append((snap, pts))

    for key, snaps in grouped.items():
        snaps.sort(key=lambda x: x[0])
        prev: int | None = None
        for snap, pts in snaps:
            if prev is None or prev != pts:
                yield key, pts, snap
            prev = pts


def build_open_interval(key: HistoryKey, total_points: int, valid_from: date) -> HistoryInterval:
    return HistoryInterval(key=key, total_points=total_points, valid_from=valid_from, valid_to=None)

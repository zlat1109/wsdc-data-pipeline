"""Parse date strings from worldsdc.com/events/ table."""

from __future__ import annotations

import re
from datetime import date, datetime

_DATE_FORMATS = ("%b %d %Y", "%B %d %Y")


def _parse_token(month: str, day: str, year: str) -> datetime | None:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(f"{month} {day} {year}", fmt)
        except ValueError:
            continue
    return None


def parse_date_range(date_str: str) -> tuple[date | None, date | None]:
    """Return (start_date, end_date) as date objects."""
    if not date_str or not str(date_str).strip():
        return None, None

    date_str = str(date_str).strip()

    pattern1 = r"(\w+)\s+(\d+)\s+(\d{4})\s*-\s*(\w+)\s+(\d+)\s+(\d{4})"
    match = re.match(pattern1, date_str)
    if match:
        sm, sd, sy, em, ed, ey = match.groups()
        start = _parse_token(sm, sd, sy)
        end = _parse_token(em, ed, ey)
        if start and end:
            return start.date(), end.date()

    pattern2 = r"(\w+)\s+(\d+)\s*-\s*(\w+)\s+(\d+),\s*(\d{4})"
    match = re.match(pattern2, date_str)
    if match:
        sm, sd, em, ed, year = match.groups()
        start = _parse_token(sm, sd, year)
        end = _parse_token(em, ed, year)
        if start and end:
            return start.date(), end.date()

    pattern3 = r"(\w+)\s+(\d+)\s*-\s*(\d+),\s*(\d{4})"
    match = re.match(pattern3, date_str)
    if match:
        month, sd, ed, year = match.groups()
        start = _parse_token(month, sd, year)
        end = _parse_token(month, ed, year)
        if start and end:
            return start.date(), end.date()

    pattern5 = r"(\w+)\s+(\d+),\s*(\d{4})"
    match = re.match(pattern5, date_str)
    if match:
        month, day, year = match.groups()
        single = _parse_token(month, day, year)
        if single:
            d = single.date()
            return d, d

    pattern6 = r"(\w+)\s+(\d+)\s+(\d{4})"
    match = re.match(pattern6, date_str)
    if match:
        month, day, year = match.groups()
        single = _parse_token(month, day, year)
        if single:
            d = single.date()
            return d, d

    return None, None


def edition_month_candidates(start: date | None, end: date | None) -> list[tuple[int, int]]:
    """Year/month pairs used to match WSDC points editions."""
    if not end:
        return []
    candidates: list[tuple[int, int]] = [(end.year, end.month)]
    if start and (start.year, start.month) != (end.year, end.month):
        candidates.append((start.year, start.month))
    return candidates

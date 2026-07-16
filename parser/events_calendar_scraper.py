"""Scrape WSDC Events Calendar from https://worldsdc.com/events/calendar/.

The page embeds FullCalendar 6 with an inline `events: [...]` JSON array.
One HTTP GET yields the full feed (no per-month API).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests

logger = logging.getLogger(__name__)

CALENDAR_URL = "https://worldsdc.com/events/calendar/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

_EVENTS_KEY_RE = re.compile(r'"events"\s*:\s*\[')


def _extract_json_array_at(html: str, open_bracket: int) -> str:
    """Return the JSON array substring starting at `open_bracket` (`[`)."""
    depth = 0
    in_string = False
    escape = False
    for i in range(open_bracket, len(html)):
        ch = html[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return html[open_bracket : i + 1]
    raise ValueError("Unterminated FullCalendar events array")


def extract_calendar_events_json(html: str) -> list[dict[str, Any]]:
    """Parse the FullCalendar events array from calendar page HTML."""
    match = _EVENTS_KEY_RE.search(html)
    if not match:
        raise ValueError("FullCalendar events array not found in calendar HTML")
    open_bracket = match.end() - 1  # points at '['
    raw = _extract_json_array_at(html, open_bracket)
    try:
        events = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse FullCalendar events JSON: {exc}") from exc
    if not isinstance(events, list):
        raise ValueError(f"Expected events list, got {type(events).__name__}")
    return [e for e in events if isinstance(e, dict)]


def scrape_events_calendar(
    *,
    url: str = CALENDAR_URL,
    timeout: float = 60.0,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    """Fetch calendar HTML and return raw FullCalendar event dicts."""
    sess = session or requests.Session()
    response = sess.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        timeout=timeout,
    )
    response.raise_for_status()
    events = extract_calendar_events_json(response.text)
    logger.info("Scraped %s calendar events from %s", len(events), url)
    return events

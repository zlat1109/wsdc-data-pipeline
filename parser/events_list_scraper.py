"""Scrape WSDC Events List from https://www.worldsdc.com/events/ (Playwright)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from parser.events_list_dates import parse_date_range

logger = logging.getLogger(__name__)

EVENTS_URL = "https://www.worldsdc.com/events/"

_EXTRACT_JS = """
() => {
    const events = [];
    const rows = document.querySelectorAll('table tbody tr');

    function containsHiatus(text) {
        if (!text) return false;
        const t = text.toLowerCase();
        return t.includes('hiatus') || t.includes('пропуск');
    }

    rows.forEach(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length < 3) return;

        const date = cells[0].textContent.trim();
        const nameCell = cells[1];
        const nameLink = nameCell.querySelector('.event_name a') || nameCell.querySelector('a');
        let name = nameLink ? nameLink.textContent.trim() : nameCell.textContent.trim();
        const typeEl = nameCell.querySelector('.event_type');
        const eventType = typeEl ? typeEl.textContent.trim() : '';
        const url = nameLink ? nameLink.href : '';
        let location = cells[2] ? cells[2].textContent.trim() : '';
        if (!location && cells.length > 3) {
            location = cells[3].textContent.trim();
        }

        let countryFlag = '';
        for (const cell of cells) {
            const img = cell.querySelector('img[data-flag]');
            if (img) {
                countryFlag = img.getAttribute('data-flag') || '';
                break;
            }
        }

        const canceled = (row.className || '').includes('event-canceled');
        const onHiatus = containsHiatus(name) || containsHiatus(row.textContent || '');

        if (!name) return;

        events.push({
            date,
            name,
            event_type: eventType,
            url,
            location,
            country_flag: countryFlag,
            canceled,
            on_hiatus: onHiatus,
        });
    });
    return events;
}
"""


@dataclass
class ScrapeResult:
    events: list[dict[str, Any]] = field(default_factory=list)
    parse_errors: list[dict[str, str]] = field(default_factory=list)


async def _scrape_async() -> ScrapeResult:
    from playwright.async_api import async_playwright

    logger.info("Scraping %s", EVENTS_URL)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(EVENTS_URL, wait_until="load", timeout=60000)
            await page.wait_for_selector("table tbody tr", timeout=30000)
            raw_rows: list[dict[str, Any]] = await page.evaluate(_EXTRACT_JS)
        finally:
            await browser.close()

    events: list[dict[str, Any]] = []
    parse_errors: list[dict[str, str]] = []

    for row in raw_rows:
        name = row.get("name") or ""
        date_str = row.get("date") or ""
        start, end = parse_date_range(date_str)
        if not start:
            parse_errors.append({"name": name, "date": date_str})
            logger.warning("Date parse failed: %r — %r", name, date_str)
            continue

        events.append(
            {
                "original_date": date_str,
                "event_name": name,
                "event_type_raw": row.get("event_type") or "",
                "url": row.get("url") or "",
                "location_raw": row.get("location") or "",
                "country_flag": row.get("country_flag") or "",
                "canceled": bool(row.get("canceled")),
                "on_hiatus": bool(row.get("on_hiatus")),
                "start_date": start.isoformat(),
                "end_date": (end or start).isoformat(),
            }
        )

    logger.info("Scraped %s events (%s parse errors)", len(events), len(parse_errors))
    return ScrapeResult(events=events, parse_errors=parse_errors)


def scrape_events_list() -> ScrapeResult:
    """Synchronous entry point for scripts and CI."""
    return asyncio.run(_scrape_async())

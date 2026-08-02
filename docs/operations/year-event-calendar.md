# Year Event Calendar

Public analytics page: year grid → Thu–Sun weekend map → event card.

## Data

Built by `scripts/build_year_event_calendar.py` from:

- `edition_calendar_dates.csv` / `event_editions.csv` (day-precision starts)
- `scheduled_events.csv` (confirmed / cancelled / hiatus + Registry|Trial)
- `event_catalog.csv` (url, typical city/country)
- `location_info.csv` (lat/lon when `coordinates_valid`)

Writes `static/data/events_year_calendar.json` on the analytics site (via `--site-repo` or `sync_analytics_site.sh`).

## Status rules

| Status | Meaning |
|--------|---------|
| `confirmed` | Published / scheduled / occurred with day date |
| `expected` | Projected from prior-year start (±1 week, WSDC Registry Rules 1.4.1) when no confirmed/cancelled/hiatus row for that `event_id` in the target year |
| `cancelled` / `hiatus` | From calendar scrape flags |

Expected rows stay until explicit hiatus/cancelled (product rule; may change later).

## Spike

```bash
python scripts/build_year_event_calendar.py --data-dir data --spike 2025 2026
```

## Site

- Page: `events-calendar.html` (EN/RU/ES) — direct URL only for now (not in site chrome / homepage nav)
- Refresh: `scripts/sync_analytics_site.sh` after full-parse export

# Year Event Calendar

Public analytics page: year grid → day map → event card.

## Data

Built by `scripts/build_year_event_calendar.py` from:

- `edition_calendar_dates.csv` / `event_editions.csv` (day-precision starts + `location_id`)
- `scheduled_events.csv` (confirmed / cancelled / hiatus + Registry|Trial)
- `event_catalog.csv` (url, typical city/country)
- `location_info.csv` (lat/lon when `coordinates_valid`)

Writes `static/data/events_year_calendar.json` on the analytics site (via `--site-repo` or `sync_analytics_site.sh`).

## Status rules

| Status | Meaning |
|--------|---------|
| `confirmed` | Published / scheduled / occurred with day date |
| `expected` | Projected from the **latest confirmed** edition before the target year (±1 week match vs any confirmed start already in that year, WSDC Registry Rules 1.4.1). Emitted for `as_of.year .. as_of.year + expected_horizon_years` (default: same as `year_radius`, typically current + 2). Skipped when the target year already has confirmed/cancelled/hiatus, or when the series' latest status before the target year is cancelled/hiatus. |
| `cancelled` / `hiatus` | From calendar scrape flags |

Years beyond the expected horizon keep only `scheduled_events` rows (no YoY gray flood from scrape noise). Empty years (no day-precision dates) are omitted from the selector. Inactive/merged catalog ids are not projected. Nameless/`nan` rows are dropped after catalog enrichment.

- Missing `location_id` on schedule rows inherits the latest edition `location_id`, then `location_info` coords (city/country fallback).
- Missing `end_date` inherits duration from another edition of the same `event_id`, else the Sunday of the Thu–Sun weekend containing `start_date`.
- Ghost / inactive duplicate ids are remapped via `MERGE_EVENT_ID_MAP`; remaining same-weekend title variants collapse by name fingerprint (e.g. Boston Tea Party vs The Boston Tea Party).
- **Registry vs Trial (`kind`)**: live `scheduled_events` Trial flags are trusted; expected YoY rows are always Registry; after a series' first points year, Trial-in-title/catalog does not stick; from **2025+**, first points year (`event_catalog.first_edition_year` / editions with results) marks that year as Trial (heuristic after the registry-points-at-trial rule change).
- Drop `edition_calendar_dates` rows whose `calendar_title` does not match the assigned `event_name` (guards URL mis-matches such as Soul Flow hiatus → Global Grand Prix). Distinct weekends for the same `event_id`+year are kept separately.
- **Stale expected**: past years never keep `expected`. In the current year, expected rows are dropped once their end date + **7 days** is before `as_of` (projected weekend passed without confirm / hiatus / cancel). Official hiatus/cancelled remain.

Each event includes `continent` in `{America, Europe, Asia, Australia}` (South America → America).

## Spike

```bash
python scripts/build_year_event_calendar.py --data-dir data --spike 2025 2026
```

## Site

- Page: `events-calendar.html` (EN/RU/ES)
- Refresh: `scripts/sync_analytics_site.sh` after full-parse export

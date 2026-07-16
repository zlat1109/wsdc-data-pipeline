# WSDC Events Calendar

Day-precision dates from [worldsdc.com/events/calendar/](https://worldsdc.com/events/calendar/).

## Live pipeline

Tuesday `sync-events-list.yml` scrapes the list **and** this calendar in one job:

1. Upsert `core.edition_calendar_dates` (durable; survives points rebuild)
2. `rebuild_event_catalog` copies onto `event_editions.start_date` / `end_date`
3. Artifacts committed under `data/events_calendar/`

Hiatus / cancelled rows are stored with `calendar_status`; editions get **no** start/end and `event_occurred=false`. Unconfirmed keeps planned dates; results (edition row) confirm occurrence.

## Usage

```bash
# Default: start_date >= 2025-01-01 + DB upsert
python scripts/sync_events_calendar.py

# Include everything in the feed
python scripts/sync_events_calendar.py --all-years

# Artifacts only
python scripts/sync_events_calendar.py --skip-db
```

## Artifacts

| File | Purpose |
|------|---------|
| `current.json` | Full normalized snapshot |
| `events_calendar.csv` | Flat calendar dates |
| `edition_date_matches.csv` | Match audit vs editions |
| `match_report.json` | Coverage summary |

## Limits

- Pre-2024 history is not on this calendar.
- Default filter drops Dec-start NYE weekends for Jan-bucketed 2025 editions — use `--all-years` for those.
- Bad ends (year wrap / sentinel) → flagged, `end_date` cleared.

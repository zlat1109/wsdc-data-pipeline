# WSDC Events List (worldsdc.com/events/)

Weekly sync of the official upcoming events schedule.

## Files

| Path | Purpose |
|------|---------|
| `current.json` | Latest full snapshot (all events on the site) |
| `events_list.csv` | Same data for Tableau / spreadsheets |
| `changelog/latest.json` | Last run: added / removed / counts |
| `changelog/run_*.json` | History of each sync run |

## Supabase

| Table / view | Role |
|--------------|------|
| `core.events_list_current` | **Latest snapshot** — one row per logical event (nearest upcoming edition) |
| `core.scheduled_events` | **Edition archive** — all `source_fingerprint` observations (`is_active` = on site now) |
| `history.events_list_runs` | Run metadata |
| `history.events_list_changes` | Added/removed log per run |
| `export.scheduled_events` | Tableau view → `events_list_current` (one row per event) |
| `export.scheduled_event_editions` | All active editions (multi-year listings on site) |
| `export.scheduled_events_legacy` | **Deprecated** — old edition-level shape for existing dashboards |

## Tableau migration (2026-06)

`export.scheduled_events` now reads from `core.events_list_current` (165 brands, not 176 editions).

| Need | View |
|------|------|
| One row per event (nearest date) | `export.scheduled_events` |
| Every future date on the site | `export.scheduled_event_editions` |
| Old workbook without changes | `export.scheduled_events_legacy` |

New columns on `export.scheduled_events`: `schedule_event_key`, `canonical_event_id`, `canonical_name`, `match_status`, `upcoming_editions`. Removed: `is_active`, `first_seen_at`, `last_seen_at`.

## Commands

```bash
# Full sync (scrape + diff + DB + Telegram if secrets set)
python scripts/sync_events_list.py

python scripts/sync_events_list.py --dry-run          # scrape + files only
python scripts/sync_events_list.py --skip-db          # no Supabase
python scripts/sync_events_list.py --skip-telegram    # no Telegram

python scripts/telegram_notify.py events-list         # resend last changelog
```

## Schedule

GitHub Action `.github/workflows/sync-events-list.yml` — **every Tuesday 08:00 UTC**.

Telegram tag: `#WSDC_Events_List`

## Mapping analysis (Events List ↔ points catalog)

Compare schedule to historical `core.events` / `core.event_instances`:

```bash
python scripts/analyze_events_list_mapping.py
```

Report: `data/events_list/mapping/latest.json`

| Section | Meaning |
|---------|---------|
| `confirmed` | URL or strong name match + location OK |
| `manual_review_required` | Fuzzy match or location drift |
| `new_events` | Not in points catalog yet (new brand / trial) |
| `location_drifts` | Same event, different location string on site |

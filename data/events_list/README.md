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

- `core.scheduled_events` — current catalog (`is_active = true`)
- `history.events_list_runs` — run metadata
- `history.events_list_changes` — added/removed log per run
- `export.scheduled_events` — Tableau view

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

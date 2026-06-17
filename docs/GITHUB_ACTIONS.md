# GitHub Actions setup

## Required repository secrets

Settings → **Secrets and variables** → **Actions** → **New repository secret**  
Direct link: https://github.com/zlat1109/wsdc-data-pipeline/settings/secrets/actions

### GitHub Actions must use the Supabase **pooler** (IPv4)

Supabase **Direct** host (`db.<ref>.supabase.co`) is **IPv6-only**. GitHub runners have no IPv6 route → `Network is unreachable`.

| Secret | Local `.env` (Direct) | GitHub Secrets (pooler, Session mode) |
|---|---|---|
| `DB_HOST` | `db.tougqwxmahkwnaculiju.supabase.co` | `aws-1-eu-west-2.pooler.supabase.com` |
| `DB_PORT` | `5432` | **`6543`** (Transaction pooler; Session `:5432` may fail) |
| `DB_NAME` | `postgres` | `postgres` |
| `DB_USER` | `postgres` | `postgres.tougqwxmahkwnaculiju` |
| `DB_PASSWORD` | same password | same password |

Copy host/port/user from Supabase Dashboard → **Connect** → **Transaction pooler** (not Direct, not Session if auth fails).

Region prefix is often `aws-1-` (not `aws-0-`) for newer projects.

Optional (not required for probe today):

| Secret | Value |
|---|---|
| `GOOGLE_MAPS_API_KEY` | For future cloud parser (geocoding) |
| `TELEGRAM_BOT_TOKEN` | Same bot token as `wsdc-telegram-bot` — probe + pipeline notifications |
| `TELEGRAM_CHAT_ID` | Test channel ID (e.g. `-4228074878`) or production channel |

Password is the same as in Supabase → Project Settings → Database. No quotes in the secret value.

### Telegram notifications

After every **check-updates** run → message `#WSDC_Pipeline_Check` (ready or not, pending/matched/missing events).

When gate opens (`changed`) → message `#WSDC_Pipeline_Parse_Start` (watermark, parse range 1..live_max, events, ETA).

After successful **full-parse** (preprocess → load → export) → message `#WSDC_Pipeline_Complete` (run_id, watermark, CSV commit status, **combined quality log** summary).

### Data quality log

Before load, `scripts/preprocess_data.py` writes `data/quality_reports/latest.json` with three blocks:

- **`before_processing`** — raw defects before normalization
- **`applied_normalizations`** — rules that ran (maps + auto year-strip)
- **`manual_review_required`** — remaining issues; `"is_new": true` needs your decision

Add fixes to `transform/data_preprocessing.py` based on `manual_review_required`, not on items already in `applied_normalizations`.

Requires `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` in this repo's Actions secrets.

**Events list sync** → message `#WSDC_Events_List` (added/removed counts, sample names). Weekly Tuesday run.

### `sync-events-list.yml`

- **Schedule**: every **Tuesday 08:00 UTC** (~10:00 Europe/Madrid)
- Scrapes https://www.worldsdc.com/events/ (Playwright)
- Writes `data/events_list/current.json`, `events_list.csv`, `changelog/run_*.json`
- Loads `core.scheduled_events` (edition archive), `core.events_list_current` (one row per event), and `history.events_list_changes` in Supabase
- Commits `data/events_list/` to repo
- Manual: Actions → **Sync WSDC Events List** → Run workflow

Local:

```bash
python db/apply.py
python scripts/sync_events_list.py
```

## Workflows

### `check-updates.yml`

**Status:** auto-schedule **paused** (manual `workflow_dispatch` only). See [MANUAL_PIPELINE.md](MANUAL_PIPELINE.md).

When re-enabled:

- **Schedule** (Mon–Fri, Europe/Madrid; GitHub may delay scheduled runs):
  - **Mon**: **20:00** only
  - **Tue–Fri**: **07:00** and **20:00**
  - CEST (summer): crons `05:00` / `18:00` UTC (Tue–Fri AM / Mon–Fri PM)
  - CET (winter): same crons → **08:00** / **21:00** local on Tue–Fri, Mon **21:00**
- **New-ID scan**: linear probe from last known max dancer ID (watermark)
- New WSDC registry numbers after weekend events → `changed`
- **Weekly cooldown**: after one successful full parse in the current Madrid week, probe stays monitoring-only and does not auto-trigger another full-parse until next Monday
- Stores probe result in `history.parse_runs` (`max_dancer_id_watermark`, `new_dancer_ids`)
- If changed → triggers `full-parse.yml`

#### How detection works (matches manual workflow)

1. WSDC assigns new dancer IDs when people first earn points (Newcomer/Novice, etc.)
2. After weekend events, new IDs appear Mon–Fri the following week
3. Script scans live max ID above DB watermark
4. **Event coverage gate**: scans weekend snapshots (newest first), skips events already in Supabase for that edition (`results_year` / `results_month`)
5. Waits until live data from new dancer IDs covers **all pending** upcoming events (e.g. Baltic Swing — not last week's J&J / Orange Blossom once loaded)
6. **`changed` only when** new IDs exist **and** all pending events are present in live data → then triggers full-parse

Watermark sources: `MAX(dancer_id)` from `core.dancers` (primary) → last probe record → `PROBE_ANCHOR_ID` env.

**Weekend snapshots (automated):** `wsdc-telegram-bot` weekly bot pushes `data/weekend_events/` here after each Thursday post. See `wsdc-telegram-bot/docs/PIPELINE_SNAPSHOT_SYNC.md`. One-time secret: `WSDC_PIPELINE_SYNC_TOKEN` in the **telegram-bot** repo (not here).

### `full-parse.yml`

Manual or auto-triggered pipeline:

1. **`cloud_parse.py --full`** (when `parse_full=true`) — HTTP fetch **every dancer ID 1..live_max**, replace `dancer_role_info`, `dancers_points_info`, `dancers_results_info` in `data/`. Needed because existing dancers get new results too, not only new registry IDs.
2. `db/apply.py` — pending migrations
3. `load.py` — CSV → Supabase (skipped with `export_only=true`)
4. `export.py` — Supabase → `data/*.csv` (legacy 5 + `event_catalog`, `event_editions`, `scheduled_events`)
5. Git commit + push `data/*.csv`

Optional export flag (manual/local only): `--include-results-by-event` adds ~47 MB `results_by_event.csv`.
Default CI export uses joins in Tableau instead (catalog + editions + `dancers_results_info`).

**Timing:** ~28k IDs × 0.3s delay ≈ 2–3 h. Workflow timeout is 360 min.

**check-updates** auto-trigger uses `parse_full=true` (not new-ID-only).

Legacy `parse_new_only=true` remains for manual debugging only.

**Manual run:** Actions → Full WSDC parse pipeline → Run workflow

Options:

- `export_only=true` — refresh Tableau CSV from current Supabase state
- `export_only=false` — loads from `data/` (committed CSVs) by default

## Until cloud parser is enabled

When `check-updates` detects a change:

1. Run parser on your laptop (notebook or script)
2. Copy fresh parser CSVs to `data/` in the repo (or run parser locally first)
3. Commit and push, or re-run **full-parse** workflow

Cloud notebook parsing (2–3 h, Selenium, IP limits) will be added after a test run.

## Test probe locally

```bash
source .venv/bin/activate
python scripts/check_updates.py --write-probe
```

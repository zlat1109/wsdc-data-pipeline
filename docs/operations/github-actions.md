# GitHub Actions setup

## Documentation automation

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `docs-check.yml` | Pull request (migrations, export, quality checks, docs) | Run `sync_docs.py --check` + `mkdocs build --strict` |
| `docs.yml` | Push to `main` (same paths + `docs/**`) | `sync_docs.py` → commit auto sections → deploy GitHub Pages |

Local before PR:

```bash
python scripts/sync_docs.py
```

Mechanical sections (migration index, export map, quality check tables, `_generated/`) sync from code. Narrative docs in `docs/architecture/`, `docs/tableau/`, etc. still need manual edits when behavior changes.

## Required repository secrets

Settings → **Secrets and variables** → **Actions** → **New repository secret**  
Direct link: https://github.com/zlat1109/wsdc-data-pipeline/settings/secrets/actions

### GitHub Actions must use the Supabase **pooler** (IPv4)

Supabase **Direct** host (`db.<ref>.supabase.co`) is **IPv6-only**. GitHub runners have no IPv6 route → `Network is unreachable`.

| Secret | Local `.env` (Direct) | GitHub Secrets (pooler, Transaction mode) |
|---|---|---|
| `DB_HOST` | `db.<your-project-ref>.supabase.co` | `aws-1-eu-west-2.pooler.supabase.com` |
| `DB_PORT` | `5432` | **`6543`** (Transaction pooler; Session `:5432` may fail) |
| `DB_NAME` | `postgres` | `postgres` |
| `DB_USER` | `postgres` | `postgres.<your-project-ref>` |
| `DB_PASSWORD` | same password | same password |

Copy host/port/user from Supabase Dashboard → **Connect** → **Transaction pooler** (not Direct, not Session if auth fails).

Region prefix is often `aws-1-` (not `aws-0-`) for newer projects.

Optional (not required for probe today):

| Secret | Value |
|---|---|
| `GOOGLE_MAPS_API_KEY` | Events-list trial geo + optional geocode |
| `TELEGRAM_BOT_TOKEN` | Same bot token as `wsdc-telegram-bot` — probe + pipeline notifications |
| `TELEGRAM_CHAT_ID` | Test channel ID (e.g. `-4228074878`) or production channel |
| `WSDC_BOT_SYNC_TOKEN` | Dispatch CSV sync to `wsdc-telegram-bot` |
| `WSDC_ANALYTICS_DEPLOY_TOKEN` | Push homepage KPIs + secondary-role JSON to `wsdc-analytics/wsdc-analytics.github.io` |

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

### Multi-machine sync

If load succeeded in CI but CSV commit failed, or you parse on another laptop, see **[data-sync.md](data-sync.md)** before the next load.

Requires `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` in this repo's Actions secrets.

**Events list sync** → message `#WSDC_Events_List` (added/removed counts, sample names). Weekly Tuesday run.

### `sync-events-list.yml`

- **Schedule**: every **Tuesday 08:00 UTC** (~10:00 Europe/Madrid)
- Scrapes https://www.worldsdc.com/events/ (Playwright) **and** https://worldsdc.com/events/calendar/ (HTTP FullCalendar JSON)
- Writes `data/events_list/` + `data/events_calendar/`
- Loads `core.scheduled_events`, `core.events_list_current`, `history.events_list_changes`
- Upserts `core.edition_calendar_dates`, then `rebuild_event_catalog` (copies day dates onto `event_editions`)
- Commits `data/events_list/` and `data/events_calendar/` to repo
- Manual: Actions → **Sync WSDC Events List** → Run workflow

Local:

```bash
python db/apply.py
python scripts/sync_events_list.py
# calendar-only:
python scripts/sync_events_calendar.py
```

## Workflows

### `check-updates.yml`

- **Schedule** (Mon–Fri, Europe/Madrid; GitHub may delay scheduled runs):
  - **Mon**: **20:00** only
  - **Tue–Fri**: **07:00** and **20:00**
  - CEST (summer): crons `05:00` / `18:00` UTC (Tue–Fri AM / Mon–Fri PM)
  - CET (winter): same crons → **08:00** / **21:00** local on Tue–Fri, Mon **21:00**
- **New-ID scan**: linear probe from last known max dancer ID (watermark)
- New WSDC registry numbers after weekend events → `changed`
- **Weekly cooldown**: after one successful full parse in the current Madrid week, probe does not auto-trigger another **registry-only** parse (`gate_status=all_loaded`) until next Monday. **Partial gate** (weekend events appearing in live) can trigger multiple full parses in the same week.
- Stores probe result in `history.parse_runs` (`max_dancer_id_watermark`, `new_dancer_ids`)
- If changed → triggers `full-parse.yml`

#### How detection works (matches manual workflow)

1. WSDC assigns new dancer IDs when people first earn points (Newcomer/Novice, etc.)
2. After weekend events, new IDs appear Mon–Fri the following week
3. Script scans live max ID above DB watermark
4. **Event coverage gate (partial-readiness)**: scans weekend snapshots (newest first), skips events already in Supabase for that edition (`results_year` / `results_month` or `start_date` month). **Future weekends are excluded** — probe only waits for events whose `end_date` is before today.
5. **`changed` when** new IDs exist **and** at least one pending event is visible in live WSDC data but not yet in Supabase → triggers **full** parse (`parse_full=true`, entire registry 1..live_max). Does **not** wait for all pending events.
6. Straggler events (e.g. delayed Neverland) carry over to the next week; no forced Friday parse for missing events.

**Quiet weekend:** if snapshots contain no concluded events, check-updates stays `unchanged` even when new dancer IDs exist.

**Parse in flight:** while a full-parse run is active (load ``running`` or probe trigger awaiting success), probe suppresses duplicate triggers. `full-parse.yml` uses concurrency group `wsdc-full-parse`.

Watermark sources: `MAX(dancer_id)` from `core.dancers` (primary) → last probe record → `PROBE_ANCHOR_ID` env.

`check-updates.yml` sets `PROBE_SLOT=evening` for the 20:00 Madrid cron and `morning` for 07:00 (reserved for future slot-specific logic).

**Weekend snapshots (automated):** `wsdc-telegram-bot` pushes `data/weekend_events/` here after Thursday weekly, after results-bot, and via weekday reconcile (`sync-weekend-snapshots.yml`). See `wsdc-telegram-bot/docs/PIPELINE_SNAPSHOT_SYNC.md`. Secret: `WSDC_PIPELINE_SYNC_TOKEN` in the **telegram-bot** repo (not here).

**Bot CSV sync (automated):** after a successful CSV commit, `full-parse.yml` dispatches `pipeline-csv-updated` to **wsdc-telegram-bot**. Secret in **this** repo: `WSDC_BOT_SYNC_TOKEN` (PAT with `contents:read` here + dispatch/write on bot). Bot pulls via `scripts/sync_csv_from_pipeline.sh` (`sync-data.yml`).

**Analytics site sync (automated):** after every successful full-parse export, `scripts/sync_analytics_site.sh` rebuilds `homepage_kpis.json` + `secondary_country_unified.json` and pushes to [wsdc-analytics.github.io](https://wsdc-analytics.github.io/). Secret in **this** repo: `WSDC_ANALYTICS_DEPLOY_TOKEN` (write on `wsdc-analytics/wsdc-analytics.github.io`). See [analytics-site-sync.md](analytics-site-sync.md).

### `full-parse.yml`

Concurrency: `wsdc-full-parse` (no parallel runs; queue if probe triggers while previous parse still running).

Two jobs so a load/export failure does **not** re-hit the WSDC points API:

1. **`parse`** (only when `parse_full` or `parse_new_only`) — `cloud_parse.py`, then upload `parser-csvs` artifact (30 days).
2. **`pipeline`** — download that artifact (or use committed `data/` if parse was skipped) → migrations → preprocess → load → export → git commit.

If **pipeline** fails after a successful **parse**: Actions → the run → **Re-run failed jobs**. GitHub reuses the artifact; WSDC is not parsed again.

`load.py` rolls back `promote_core` on error (does not commit an empty `core.results`). Staging CSVs stay in Supabase from the earlier staging COPY commit.

Manual or auto-triggered pipeline:

1. **`cloud_parse.py --full`** (when `parse_full=true`) — HTTP fetch **every dancer ID 1..live_max**, replace `dancer_role_info`, `dancers_points_info`, `dancers_results_info` in `data/`. Needed because existing dancers get new results too, not only new registry IDs.
2. `db/apply.py` — pending migrations
3. `load.py` — CSV → Supabase (skipped with `export_only=true`)
4. `export.py` — Supabase → `data/*.csv` + `data/event_aliases.json` (merged alias maps for bot)
5. Git commit + push `data/*.csv` and `data/event_aliases.json`
6. If CSV commit succeeded → `repository_dispatch` to **wsdc-telegram-bot** (`sync-data.yml`) when `WSDC_BOT_SYNC_TOKEN` is set
7. Rebuild + push analytics site JSON (`homepage_kpis.json`, `secondary_country_unified.json`) when `WSDC_ANALYTICS_DEPLOY_TOKEN` is set

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

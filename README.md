# WSDC Data Pipeline

Unified World Swing Dance Championships data pipeline ([points.worldsdc.com](https://points.worldsdc.com)):
parse → normalized Supabase (Postgres) → change history → CSV export for Tableau Public.

Replaces the old workflow of running the parser on two laptops and overwriting CSVs by hand.

**Docs (start here):** [zlat1109.github.io/wsdc-data-pipeline](https://zlat1109.github.io/wsdc-data-pipeline/)  
**Russian README:** [README.ru.md](README.ru.md)  
**Collaborator guide (event locations):** [docs/committee/event-locations-guide.md](docs/committee/event-locations-guide.md)

## Architecture

```
points.worldsdc.com
        │  (GitHub Actions, cron)
        ▼
   parser/          collect via HTTP API
        ▼
   staging          raw run landing (Supabase)
        ▼
   core             normalized entities: dancers, events,
        │           event_editions, locations, results, dancer_points
        │           (+ optional: competitions dump, cr_* Competition Results)
        ▼
   history          SCD2: points, divisions, names + run journal
        ▼
   export/          SQL views → CSV (1:1 with legacy file shapes)
        ▼
   data/            CSVs in git — source for Tableau Public and other projects
```

Optional enrichment (local, not in the weekly parse): Competition Results → `core.cr_*`
and the Event Data Registry on the analytics site — see
[docs/operations/competition-results.md](docs/operations/competition-results.md).

## Repository layout

| Path | Purpose |
|---|---|
| `parser/` | Parser modules (HTTP API + Selenium fallback) |
| `transform/` | Preprocess and normalization |
| `db/migrations/` | SQL migrations for `staging` / `core` / `history` |
| `export/` | Export views → CSV |
| `data/` | Exported CSVs (committed automatically) |
| `tests/` | Unit tests |
| `.github/workflows/` | `check-updates.yml`, `full-parse.yml`, … |

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill DB_* (prefer pooler) and GOOGLE_MAPS_API_KEY
```

## Usage

```bash
python -m parser.wsdc_parser      # full parse (local)
python backfill.py                # initial load of existing CSVs into the DB
python load.py                    # staging -> core -> history
python export.py                  # legacy + catalog + history -> data/*.csv
python export.py --include-results-by-event   # + results_by_event.csv (~47 MB)
python export.py --include-results-with-name  # + dancers_results_with_name.csv
```

## Output CSVs (Tableau contract)

### Legacy (unchanged for existing workbooks)

- `dancers_points_info.csv`
- `dancer_role_info.csv`
- `dancers_results_info.csv`
- `location_info.csv`
- `events_wsdc.csv`

Column names and shapes stay 1:1 with the previous process.

### Change history (SCD2 → CSV)

Exported automatically with the legacy CSVs:

| CSV | Contents |
|-----|----------|
| `changed_dancer_points_info.csv` | Points changes |
| `changed_dancer_role_info.csv` | Division changes (no name-only trigger) |
| `changed_dancer_name_info.csv` | Display-name changes (`history.dancer_names_history`) |

For the name on a **past** result: `python export.py --include-results-with-name` or join
`changed_dancer_name_info` in Tableau. See [docs/tableau/joins.md](docs/tableau/joins.md).

### Event catalog (event-centric dashboards)

Exported automatically with the legacy CSVs:

| CSV | View | Purpose |
|-----|------|---------|
| `event_catalog.csv` | `export.event_catalog` | One event = one row (name, url, typical location, stats, upcoming) |
| `event_editions.csv` | `export.event_editions` | Event × year × month (edition location, result counts) |
| `scheduled_events.csv` | `export.scheduled_events` | Current WSDC schedule (registry/trial, one row per event) |

Optional (`--include-results-by-event`):

| CSV | View | Purpose |
|-----|------|---------|
| `results_by_event.csv` | `export.results_by_event` | Results + catalog/edition joins (~47 MB) |

**Suggested Tableau Public joins** (without the heavy `results_by_event.csv`):

```
dancers_results_info  ←→  event_editions   ON event_name, event_year, event_month
event_editions        ←→  event_catalog    ON event_id
scheduled_events      ←→  event_catalog    ON canonical_event_id (= event_id)
```

See [docs/tableau/joins.md](docs/tableau/joins.md). `dancers_results_info.csv` has **no `event_id`** —
only `event_name` + year/month.

Rebuild the catalog in Supabase after a points load (`load.py`) or manually:

```bash
python scripts/build_event_catalog.py
```

### Tableau Public: weekly refresh

Tableau Public does not connect to Supabase — only local CSVs.

1. GitHub Actions (`full-parse.yml` or `export_only=true`) writes fresh CSVs under `data/` and pushes.
2. Locally: `git pull` in a `wsdc-data-pipeline` clone.
3. In Tableau: **Data → Refresh** (or reopen the workbook pointed at `data/*.csv`).

With DB access:

```bash
python export.py --output-dir ./data
```

The WSDC schedule (scrape worldsdc.com/events/ + calendar) updates on Tuesdays —
`sync-events-list.yml` commits `data/events_list/` and `data/events_calendar/`; day-precision
dates land in `core.edition_calendar_dates` and are copied into `event_editions` on rebuild.

## Documentation

**Web site:** [zlat1109.github.io/wsdc-data-pipeline](https://zlat1109.github.io/wsdc-data-pipeline/) (MkDocs Material, auto-deploy on push)

| Audience | Start here |
|----------|------------|
| Tableau analyst | [docs/tableau/index.md](docs/tableau/index.md) |
| Developer / maintainer | [docs/architecture/overview.md](docs/architecture/overview.md) |
| Operations | [docs/operations/index.md](docs/operations/index.md) |
| Collaborators (locations) | [docs/committee/event-locations-guide.md](docs/committee/event-locations-guide.md) |

Full index: [docs/index.md](docs/index.md). Local preview: `pip install -r requirements-docs.txt && mkdocs serve`

## Secrets

- Local — `.env` (gitignored).
- CI — GitHub Secrets: see [docs/operations/github-actions.md](docs/operations/github-actions.md).

## Migration status

- [x] Phase 0: parser code consolidated in this repo
- [ ] Merge with old-laptop reference version (separate PR)
- [x] Phase 1: Supabase schemas (`db/migrations/`)
- [x] Phase 2: `load.py` + `backfill.py`
- [x] Phase 3: `export.py` + views
- [x] Phase 4: GitHub Actions (`check-updates.yml`, `full-parse.yml`)
- [x] Phase 5 (partial): `wsdc-telegram-bot` — CSV auto-sync, `scheduled_events.csv`, publication ledger, advancement golden tests
- [ ] Phase 5: Tableau Public / analytics repo — switch to `main` as the sole CSV source

## Integration with wsdc-telegram-bot

After each successful CSV commit in `full-parse.yml`:

1. Pipeline pushes `data/*.csv` + `data/event_aliases.json`
2. `repository_dispatch` → bot `sync-data.yml` (secret `WSDC_BOT_SYNC_TOKEN`)
3. Bot commits fresh CSVs into its own `data/` (LFS)

Feedback path: weekly/results bot pushes weekend snapshots into the pipeline
(`WSDC_PIPELINE_SYNC_TOKEN` on the bot). See
[docs/operations/github-actions.md](docs/operations/github-actions.md).

## Integration with wsdc-analytics.github.io

After each successful full-parse export:

1. `scripts/sync_analytics_site.sh` builds site JSON (KPIs, calendars, Event Growth, …) from `data/`
2. Push to `wsdc-analytics/wsdc-analytics.github.io` (secret `WSDC_ANALYTICS_DEPLOY_TOKEN`)

See [docs/operations/analytics-site-sync.md](docs/operations/analytics-site-sync.md).

The **`old-laptop-version`** branch holds reference parser CSVs from the old laptop for comparison;
do not merge into `main` without `compare_csv_snapshots.py` / `build_merged_load_dataset.py`.

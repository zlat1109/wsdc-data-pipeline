# Tableau Public workflow

Tableau Public reads **local CSV files** from this repository. It cannot connect to Supabase directly.

## Weekly refresh (recommended)

1. GitHub Actions runs full parse (or export-only) and commits fresh CSVs to `main`.
2. On your machine:

```bash
cd wsdc-data-pipeline
git pull origin main
```

3. In Tableau: **Data → Refresh** (workbook must point to CSV paths inside your clone).

## File location

Default export directory: `data/` in repo root.

Example paths (adjust to your clone):

```text
.../wsdc-data-pipeline/data/dancers_results_info.csv
.../wsdc-data-pipeline/data/event_catalog.csv
```

If you moved the repo, update data source paths in Tableau once.

## Alternative: local export

With `.env` database credentials:

```bash
python export.py --output-dir ./data
```

Use when Supabase is ahead of git (CI load succeeded but CSV commit failed). See [../operations/data-sync.md](../operations/data-sync.md).

## Default CSV set (13 files)

| File | Purpose |
|------|---------|
| `dancers_points_info.csv` | Current points |
| `dancer_role_info.csv` | Role summaries |
| `dancers_results_info.csv` | Competition results |
| `location_info.csv` | Locations |
| `events_wsdc.csv` | Registry listing |
| `event_catalog.csv` | Event brands |
| `event_editions.csv` | Editions by year/month |
| `scheduled_events.csv` | Upcoming WSDC schedule |
| `changed_dancer_points_info.csv` | Points change history |
| `changed_dancer_role_info.csv` | Role change history |
| `divisional_structure.csv` | Division snapshots (all roles) |
| `divisional_structure_only_dominate_role.csv` | Division snapshots (dominate role) |
| `dancer_transitions.csv` | Division transitions over time |

## Optional large files

```bash
python export.py --include-results-by-event   # ~47 MB denormalized results
```

Geo views (`export.geo_events`) are not in default export — query Supabase or extend `export.py`.

## Schedule-only updates

Tuesday sync commits `data/events_list/` separately. `scheduled_events.csv` updates on next full export after sync.

## Documentation

- [csv-contract.md](csv-contract.md) — every column
- [joins.md](joins.md) — relationships
- [dashboards-migration.md](dashboards-migration.md) — scheduled events view change (2026-06)

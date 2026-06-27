# Database migrations

Schema changes are versioned SQL files in `db/migrations/`. Applied in filename order by `db/apply.py`.

## Apply workflow

```bash
python db/apply.py              # apply pending
python db/apply.py --dry-run    # preview only
python db/apply.py --check      # print connection settings (no password)
```

Each migration runs in its own transaction. Applied filenames are recorded in `public.schema_migrations` and skipped on subsequent runs.

CI and `scripts/run_pipeline.py` call `db/apply.py` before load.

## Migration index

| File | Summary |
|------|---------|
| `001_schemas.sql` | Create `staging`, `core`, `history` schemas |
| `002_staging.sql` | Staging tables mirroring parser CSVs |
| `003_core.sql` | Core entities: dancers, events, results, points, levels |
| `004_history.sql` | `parse_runs`, SCD2 points/roles history |
| `005_export_views.sql` | Initial `export.*` legacy views |
| `006_probe_watermark.sql` | Extend `parse_runs` for update checker watermark |
| `007_events_list.sql` | Schedule scrape tables + initial scheduled export |
| `008_scheduled_event_status.sql` | `status_event` on scheduled export |
| `009_events_list_current.sql` | `events_list_current`; reshape `export.scheduled_events` |
| `010_events_list_current_fk.sql` | FK from `events_list_current` to `events` |
| `011_scheduled_events_legacy_view.sql` | Deprecated `export.scheduled_events_legacy` |
| `012_event_catalog.sql` | `event_catalog`, `event_editions`, catalog export views |
| `013_lock_schema_migrations.sql` | Protect migration table |
| `014_results_location_idx.sql` | Index on `core.results.location_id` |
| `015_fk_indexes.sql` | Additional FK indexes |
| `016_results_event_name_raw.sql` | `core.results.event_name_raw` |
| `017_export_event_name_raw.sql` | Export view uses raw name fallback |
| `018_history_export_views.sql` | `export.changed_*` from history tables |
| `019_geo_event_views.sql` | `export.geo_events`, `export.results_by_geo_event` |

## Adding a migration

1. Create `db/migrations/020_description.sql` (next sequential number)
2. Use `CREATE OR REPLACE VIEW` for export changes when possible
3. Run `python db/apply.py` locally against dev/staging Supabase branch
4. Run `python export.py` and verify Tableau CSV columns
5. Regenerate doc fragments: `python scripts/generate_schema_docs.py`
6. Update this index and relevant field catalogs in `docs/database/`

## Generated documentation

```bash
python scripts/generate_schema_docs.py           # from migration SQL
python scripts/generate_schema_docs.py --live    # merge live information_schema types
```

Output: `docs/database/_generated/tables.md`, `views.md`, `export_map.md`

Hand-written narrative in `docs/database/*.md` remains authoritative for semantics; generated files help detect DDL drift.

## Documentation site

Preview locally:

```bash
pip install -r requirements-docs.txt
mkdocs serve
```

Pushes to `main` that touch `docs/` deploy to [GitHub Pages](https://zlat1109.github.io/wsdc-data-pipeline/) via `.github/workflows/docs.yml`.

## Rollback policy

No automated down migrations. Roll forward with a corrective migration. For destructive data changes, use Supabase branch snapshot before `--apply` repair scripts.

## Related

- [index.md](index.md) — schema overview
- [../operations/github-actions.md](../operations/github-actions.md) — pooler connection for CI

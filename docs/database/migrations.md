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

<!-- docs-sync:migration-index -->
| File | Summary |
|------|---------|
| `001_schemas.sql` | Schemas for the WSDC data pipeline. staging: raw per-run loads (truncated before each load) core:    normalized current state history: full change history (SCD2) + run journal |
| `002_staging.sql` | Staging tables mirror the parser CSV outputs (current laptop format, 13/9/10-column versions). All columns are text: casting and normalization happen in the load step. Tables are truncated before each load. |
| `003_core.sql` | Core: normalized current state. Canonical value format = full words ("Follower", "Intermediate", "All-Star"), matching the old-laptop CSVs that the Tableau dashboards were built on. Abbreviated forms used by the optimized parser map via core.levels. |
| `004_history.sql` | History: run journal + SCD2 change tracking. Replaces the old workflow's changed_*.csv files: instead of appending snapshot rows to ever-growing CSVs, only actual changes are stored, each as a validity interval [valid_from, valid_to). |
| `005_export_views.sql` | Export views: Tableau Public contract (old-laptop CSV format, full-word levels/roles). |
| `006_probe_watermark.sql` | Extend parse_runs for new-ID probe workflow (watermark-based detection). |
| `007_events_list.sql` | WSDC Events List: upcoming schedule + weekly change log. Independent from points load (promote_core does NOT truncate these tables). |
| `008_scheduled_event_status.sql` | Ensure status_event is always Registry Event or Trial Event on the export surface. |
| `009_events_list_current.sql` | Split schedule storage: core.scheduled_events     = edition-level archive (source_fingerprint, incl. history) core.events_list_current  = one row per logical event (nearest upcoming edition) history.*                 = run + added/removed logs (unchanged) |
| `010_events_list_current_fk.sql` | canonical_event_id comes from schedule mapping + supplement catalog; not every mapped id exists in core.events until points promote runs. |
| `011_scheduled_events_legacy_view.sql` | Legacy Tableau view: one row per active edition (pre-009 schema shape). Use export.scheduled_events for one row per event brand. |
| `012_event_catalog.sql` | Event catalog: brand-level metadata + year/month editions for Tableau / analytics. Rebuilt after each points load (see db/build_event_catalog.py). Join results: event_id + event_year + event_month = edition_key (or edition_id). |
| `013_lock_schema_migrations.sql` | Close public exposure of migration metadata (Security Advisor: rls_disabled_in_public). |
| `014_results_location_idx.sql` | Index FK columns used in catalog rebuild and location joins (schema-foreign-key-indexes). |
| `015_fk_indexes.sql` | Index unindexed foreign-key columns (schema-foreign-key-indexes). Improves JOINs, CASCADE, and filters on run_id / event_id. |
| `016_results_event_name_raw.sql` | Preserve raw API/staging event name on results (export view must not erase it). |
| `017_export_event_name_raw.sql` | Export: keep raw API event name when event_id is not resolved yet. |
| `018_history_export_views.sql` | History export views: drop-in replacement for the old workflow's changed_*.csv files (same column contract) so existing Tableau Public workbooks keep working. Source is the SCD2 history tables; each version row becomes one snapshot row with update_date = valid_from (changes only, not every weekly snapshot). |
| `019_geo_event_views.sql` | Geo-aware export views for Tableau event analytics. |
| `020_export_csv_column_alignment.sql` | Align export views with committed Tableau CSV column sets (parser-compatible extras). |
| `021_dancer_names_history.sql` | Identity history: display-name changes separate from competitive (points/divisions) history. |
| `022_dancer_name_exports.sql` | Point-in-time dancer name lookup + split history export views. |
| `023_dancer_roles_division_sig.sql` | Shared md5 signature for competitive role/division SCD2 (excludes dancer_name). |
<!-- /docs-sync:migration-index -->

## Adding a migration

1. Create `db/migrations/024_description.sql` — first comment block is the index summary (or `-- @docs-summary: one line`)
2. Use `CREATE OR REPLACE VIEW` for export changes when possible
3. Run `python db/apply.py` locally against dev/staging Supabase branch
4. Run `python scripts/sync_docs.py` (updates auto sections + `_generated/`)
5. Update hand-written narrative in `docs/database/*.md` or `docs/architecture/*.md` if semantics changed

## Generated documentation

```bash
python scripts/sync_docs.py                    # auto sections + _generated/
python scripts/generate_schema_docs.py --live  # optional: merge live column types
```

Output: `docs/database/_generated/tables.md`, `views.md`, `export_map.md`

Hand-written narrative in `docs/database/*.md` remains authoritative for semantics; `scripts/sync_docs.py` keeps mechanical sections aligned with code.

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

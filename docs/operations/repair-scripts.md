# Repair scripts

One-off database maintenance scripts. **Always run `--dry-run` first.** Prefer Supabase branch snapshot before `--apply` on production.

## Recommended order (audit remediation)

```bash
python scripts/audit_event_splits.py --output-dir data/quality_reports

python scripts/merge_event_ids.py --dry-run
python scripts/merge_event_ids.py --apply

python scripts/repair_divisions.py --dry-run
python scripts/repair_divisions.py --apply

python scripts/repair_locations.py

python scripts/dedupe_core_data.py --dry-run    # duplicate results / bloated locations (see below)
python scripts/dedupe_core_data.py --apply

python scripts/repair_results_location.py --dry-run   # if location_id gaps remain
python scripts/repair_results_location.py --apply

python scripts/cleanup_event_catalog.py --dry-run
python scripts/cleanup_event_catalog.py --apply

python scripts/reconcile_points_history.py --dry-run
python scripts/reconcile_points_history.py --apply

python scripts/reconcile_roles_history.py --dry-run
python scripts/reconcile_roles_history.py --apply

python scripts/reconcile_names_history.py --dry-run
python scripts/reconcile_names_history.py --apply

python scripts/split_legacy_role_history.py --csv path/to/changed_dancer_role_info.csv --dry-run
python scripts/split_legacy_role_history.py --csv path/to/changed_dancer_role_info.csv --apply

python scripts/seed_dancer_aliases.py --apply

python scripts/monitor_data_quality.py
python export.py --output-dir data
# export.py re-applies EVENT_NAME_LOCATION_OVERRIDES after COPY; if you
# refresh CSVs another way, run the apply script explicitly:
# python scripts/apply_event_name_location_overrides_csv.py --apply
```

Note: `repair_locations.py` has no `--dry-run`; it always applies corrections.
After any DB→CSV export, overrides must land on `dancers_results_info` /
`event_editions` / `events_wsdc` (stale Supabase otherwise undoes Champion News
fixes). `export.py` does this automatically.

## Script reference

| Script | Purpose | Mutates DB |
|--------|---------|------------|
| `audit_event_splits.py` | Classify duplicate event_name → event_id pairs | No |
| `merge_event_ids.py` | Remap `core.results.event_id` (geo gate) | Yes |
| `repair_divisions.py` | Normalize All-Stars, Champions, Masters | Yes |
| `repair_locations.py` | Apply location corrections + enrich | Yes |
| `dedupe_core_data.py` | Remove duplicate results + collapse duplicate locations | Yes |
| `repair_results_location.py` | Backfill missing `location_id` on results | Yes |
| `cleanup_event_catalog.py` | Phantom ids, inactive empty catalog rows | Yes |
| `reconcile_points_history.py` | Fix SCD2 drift vs core snapshot | Yes |
| `reconcile_roles_history.py` | Fix division history drift vs core.dancer_roles | Yes |
| `reconcile_names_history.py` | Fix name history drift vs core.dancers | Yes |
| `split_legacy_role_history.py` | Rebuild role + name history from legacy CSV | Yes |
| `seed_dancer_aliases.py` | Seed core.dancer_aliases from knowledge map | Yes |
| `backfill.py` | Initial CSV → staging → core + full history backfill | Yes |
| `close_parse_runs.py` | Close stuck `running` parse_runs | Yes |
| `apply_event_name_location_overrides_csv.py` | Remap local export CSV `location_id` from `EVENT_NAME_LOCATION_OVERRIDES` | No (CSV only) |
| `audit_event_location_mismatches.py` | Find shared wrong location_id / calendar mismatches | No |

## dedupe_core_data.py

In-place cleanup for **already loaded** Supabase data — same rules as preprocess (`dedupe_result_rows` + `dedupe_location_info` from PR #14). Does **not** re-fetch dancers from WSDC.

### When to use

| Situation | Use this script? |
|-----------|------------------|
| `core.results` has exact duplicate rows (export row count > unique competitive keys; e.g. +77 rows) | **Yes** |
| `core.locations` is inflated (many `location_id` for the same city: Phoenix USA variants, London UK variants) | **Yes** |
| Fix needed **without** waiting for a full parse / full reload | **Yes** |
| After **full parse on `main` with PR #14+** (preprocess dedupes before load) | **No** — preventive only |
| Missing / NULL `location_id` on results | **No** — use `repair_results_location.py` |
| Singapore ids 244/350 only | **No** — use `merge_location_ids.py` (this script also handles broader city dedupe) |
| Wrong `event_id` / event name splits | **No** — use `merge_event_ids.py` |

### What it does

1. Deletes duplicate `core.results` rows (keeps lowest `result_id` per business key: dancer, event, division, role, date, result, points, location).
2. Remaps `location_id` on `core.results`, `core.event_instances`, `core.event_editions` to canonical ids.
3. Deletes redundant `core.locations` rows.
4. Rebuilds event catalog + `ANALYZE`.

```bash
python scripts/dedupe_core_data.py --dry-run
python scripts/dedupe_core_data.py --apply
python scripts/validate_supabase_quality.py
python export.py --output-dir data   # optional: refresh CSVs (+ re-applies location overrides)
```

## merge_location_ids.py

Remaps `LOCATION_ID_MERGE_MAP` in `transform/knowledge/locations.py` (duplicate cities, venue labels, country typos). Also applies `LOCATION_ID_CORRECTIONS` (field patches) and clears `event_state` for non-US countries.

```bash
python scripts/merge_location_ids.py --dry-run
python scripts/merge_location_ids.py --apply
```

Updates `core.results`, `core.event_instances`, `core.event_editions`, deletes merged rows, rebuilds event catalog. Use for known duplicate pairs (Amsterdam 373→191, Anaheim 291→23, Boston Club 334→Düsseldorf 127, etc.) — see merge map in `locations.py`.

## merge_event_ids.py

Requires geo match per [../policies/event-geo-dedup.md](../policies/event-geo-dedup.md).

- Updates `core.results.event_id`
- Inserts `core.event_aliases`
- Marks source catalog `registry_status = merged`
- Calls `rebuild_event_catalog`

## reconcile_points_history.py

Closes stale open intervals; inserts missing open rows from `core.dancer_points`.

Target: `points_history_drift = 0` in monitor.

## cleanup_event_catalog.py

- Phantom title ghosts (MADjam, Midnight Madness, UK WCS, USA Grand Nationals, Kazan) → `registry_status = merged` + alias to live canonical ids (see `db/catalog_registry.py`)
- Remaining empty catalog rows → `registry_status = inactive`

## close_parse_runs.py

- GitHub Actions runs with `finished_at` → `success`
- Ancient backfill runs 1, 2 → `failed`

Valid statuses: `running`, `success`, `failed`, `skipped`.

## Related

- [quality-monitoring.md](quality-monitoring.md)
- [../database/migrations.md](../database/migrations.md)

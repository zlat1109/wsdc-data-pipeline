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
```

Note: `repair_locations.py` has no `--dry-run`; it always applies corrections.

## Script reference

| Script | Purpose | Mutates DB |
|--------|---------|------------|
| `audit_event_splits.py` | Classify duplicate event_name → event_id pairs | No |
| `merge_event_ids.py` | Remap `core.results.event_id` (geo gate) | Yes |
| `repair_divisions.py` | Normalize All-Stars, Champions, Masters | Yes |
| `repair_locations.py` | Apply location corrections + enrich | Yes |
| `repair_results_location.py` | Backfill missing `location_id` on results | Yes |
| `cleanup_event_catalog.py` | Phantom ids, inactive empty catalog rows | Yes |
| `reconcile_points_history.py` | Fix SCD2 drift vs core snapshot | Yes |
| `reconcile_roles_history.py` | Fix division history drift vs core.dancer_roles | Yes |
| `reconcile_names_history.py` | Fix name history drift vs core.dancers | Yes |
| `split_legacy_role_history.py` | Rebuild role + name history from legacy CSV | Yes |
| `seed_dancer_aliases.py` | Seed core.dancer_aliases from knowledge map | Yes |
| `backfill.py` | Initial CSV → staging → core + full history backfill | Yes |
| `close_parse_runs.py` | Close stuck `running` parse_runs | Yes |
| `monitor_data_quality.py` | SQL invariant checks | No |

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

- Phantom USA Grand Nationals ids 486–488 → alias to event_id 22
- Empty catalog rows → `registry_status = inactive`

## close_parse_runs.py

- GitHub Actions runs with `finished_at` → `success`
- Ancient backfill runs 1, 2 → `failed`

Valid statuses: `running`, `success`, `failed`, `skipped`.

## Related

- [quality-monitoring.md](quality-monitoring.md)
- [../database/migrations.md](../database/migrations.md)

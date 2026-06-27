# Repair scripts

One-off database maintenance scripts. **Always run `--dry-run` first.** Prefer Supabase branch snapshot before `--apply` on production.

## Recommended order (audit remediation)

```bash
python scripts/merge_event_ids.py --dry-run
python scripts/merge_event_ids.py --apply

python scripts/repair_divisions.py --dry-run
python scripts/repair_divisions.py --apply

python scripts/repair_locations.py

python scripts/cleanup_event_catalog.py --dry-run
python scripts/cleanup_event_catalog.py --apply

python scripts/reconcile_points_history.py --dry-run
python scripts/reconcile_points_history.py --apply

python scripts/close_parse_runs.py --apply

python scripts/monitor_data_quality.py
python export.py --output-dir data
```

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

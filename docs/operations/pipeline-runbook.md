# Pipeline runbook

Manual execution when not waiting for scheduled GitHub Actions.

Auto `check-updates` cron is **enabled** (Mon–Fri probe, auto-triggers full-parse when gate passes).

## Standard manual flow

1. **Optional:** parse locally or in CI with `parse_full=true`
2. **Validate CSVs** (fast, catches most load failures):

```bash
python scripts/validate_pipeline_inputs.py --data-dir ./data
```

3. **Load + export** (no re-parse):

```bash
python scripts/run_pipeline.py --data-dir ./data --source local
```

4. Or **export only** from current Supabase:

```bash
python scripts/run_pipeline.py --export-only
```

## GitHub Actions (manual)

| Workflow | When |
|----------|------|
| **Check WSDC updates** | Scheduled Mon–Fri; auto-triggers full-parse when probe gate passes |
| **Full WSDC parse pipeline** | Full run when you choose |

Recommended manual full-parse inputs:

- `parse_full=false` if CSVs already in `data/`
- `export_only=false`
- Run `validate_pipeline_inputs` locally first if CSVs were produced elsewhere

## CSV dtype contract (cloud_parse → preprocess)

Parser output and preprocess input treat **all columns as strings** (`cloud_parse` → `astype(str)`; `load_csv_bundle(dtype=str)`). Preprocess must not assign bare Python `int`/`float` into StringDtype columns — use `transform.pandas_utils.assign_column_values` or `cell_str()` in `parser/extract_api.py`.

## Known failure modes

| Stage | Symptom | Fix |
|-------|---------|-----|
| Preprocess | `Invalid value '47' for dtype 'str'` | Fixed in `merge_map` + `pandas_utils`; ensure ID fields are strings end-to-end |
| Load | `dancer_roles_dancer_id_fkey` | Fixed in `promote_core.sql`; run `validate_pipeline_inputs` |
| Load | invalid `event_role` / `role` | Fix in preprocess or source CSV |
| CI commit | `git push rejected (fetch first)` | `git pull --rebase` before push in `full-parse.yml` |
| Auto re-run | Multiple long parses | Weekly cooldown in `check_updates.py` |
| Load | `event_editions` = 0 | Cloud parse dates; run preprocess with date normalization |
| Sync | Supabase fresh, git CSV stale | [data-sync.md](data-sync.md); run `export.py` and commit |
| Load | `names_history_drift` > 0 | `scripts/reconcile_names_history.py --apply` |
| Load | blank dancer names after parse | Check coalesce in `promote_core.sql`; extended check `dancers_empty_name` |
| Supabase | duplicate result rows / 400+ locations | `scripts/dedupe_core_data.py --apply` — see [repair-scripts.md](repair-scripts.md#dedupe_core_datapy) |
| Supabase | non-US `event_state` (England, Alberta) | Preprocess clears on load; `merge_location_ids.py --apply` on existing DB |
| Export | row count > unique result keys | Run dedupe on Supabase or wait for preprocess on next full parse (PR #14+) |

## Multi-machine

See [data-sync.md](data-sync.md).

## Tests before a manual run

```bash
pytest tests/test_pipeline_validation.py tests/test_preprocess_with_log.py tests/test_normalize_results_dates.py -q
python scripts/validate_pipeline_inputs.py --data-dir ./data
```

## Automation schedule

`.github/workflows/check-updates.yml` — see [github-actions.md](github-actions.md).

## Related

- [../architecture/overview.md](../architecture/overview.md)
- [quality-monitoring.md](quality-monitoring.md)

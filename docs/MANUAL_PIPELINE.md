# Manual pipeline mode (until auto-schedule is re-enabled)

Auto `check-updates` cron is **paused**. Run updates manually when ready.

## Quick checklist

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
| **Check WSDC updates** | Probe only — does **not** auto-trigger full-parse while schedule is off |
| **Full WSDC parse pipeline** | Full run when you choose |

Recommended manual full-parse inputs:
- `parse_full=false` if CSVs already in `data/`
- `export_only=false`
- Run `validate_pipeline_inputs` locally first if CSVs were produced elsewhere

## Known failure modes (and fixes)

| Stage | Symptom | Fix |
|-------|---------|-----|
| Load | `dancer_roles_dancer_id_fkey` | Fixed in `promote_core.sql` (empty names); run `validate_pipeline_inputs` |
| Load | invalid `event_role` / `role` | Fix in `transform/data_preprocessing.py` or source CSV |
| CI commit | `git push rejected (fetch first)` | Fixed: `git pull --rebase` before push in `full-parse.yml` |
| Auto re-run | Multiple 4h parses / minutes burn | Schedule paused + weekly cooldown when re-enabled |
| Load | `event_editions` = 0 after load | Cloud parse dates; run preprocess with `normalize_results_dates` |
| Sync | Supabase fresh, git CSV stale | See [DATA_SYNC.md](DATA_SYNC.md); run `export.py` and commit |
| Geography | Map markers split by suburb | Fixed in preprocess (`transform/geography`); use `preprocess_data.py` before load, not `sync_locations_from_csv` alone |

## Multi-machine / migration

See **[DATA_SYNC.md](DATA_SYNC.md)** — golden rules when moving between laptops or merging `old-laptop-version` into `main`.

## Tests before a manual run

```bash
pytest tests/test_pipeline_validation.py tests/test_preprocess_with_log.py tests/test_normalize_results_dates.py -q
python scripts/validate_pipeline_inputs.py --data-dir ./data
```

## Re-enable automation

Uncomment `schedule` in `.github/workflows/check-updates.yml` and push when pipeline is stable.

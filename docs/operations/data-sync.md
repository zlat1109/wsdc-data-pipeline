# Data sync

Use when switching machines, merging branches, or making `main` the single source of truth.

## What went wrong (June 2026)

Three copies of truth diverged:

| Source | Typical state | Risk |
|--------|---------------|------|
| **Supabase** | Updated by CI load even when git push failed | DB ahead of repo |
| **`main` / GitHub CSV** | Stale export | Tableau/repo behind DB |
| **Old laptop branch** | Fresh parser CSV, no export tables | Different row counts + IDs |
| **GitHub cloud parse** | Raw API dates (`January 1997`) | Load succeeds but `event_editions` empty |

CI can **succeed through load + export** and still leave **GitHub CSV stale** if the commit step fails.

## Golden rules

1. **Supabase is not automatically mirrored to git.** After every successful load, verify CSV commit on `main` or run `export_only` and commit manually.

2. **Parser CSV ≠ export CSV.**
   - Parser: `dancer_role_info`, `dancers_points_info`, `dancers_results_info`, `location_info`, `events_wsdc`
   - Export (from DB): `event_catalog`, `event_editions`, `scheduled_events`

3. **Cloud parse always needs preprocess before load.** Without date normalization, `event_editions` stays 0.

4. **Compare before reload:**

```bash
python scripts/compare_csv_snapshots.py --local-dir ./data
```

5. **Merged reload** (when machines diverged):

```bash
python scripts/build_merged_load_dataset.py --output-dir data/merged_load
python scripts/validate_pipeline_inputs.py --data-dir data/merged_load
python scripts/preprocess_data.py --data-dir data/merged_load --source local
python load.py --data-dir data/merged_load --source local
python export.py
```

6. **Machine switch checklist**
   - `git pull --rebase origin main`
   - Compare local `data/*.csv` to `main`
   - One authoritative parse per week
   - After load: `export.py` → commit `data/*.csv`

7. **CI / pooler:** GitHub Actions must use Supabase transaction pooler — [github-actions.md](github-actions.md).

## Expected row counts (mid-2026)

| File | ~rows |
|------|-------|
| `dancer_role_info` | 27,150–27,200 |
| `dancers_points_info` | 50,500 |
| `dancers_results_info` | 194,000+ |
| `event_editions` | 2,600+ (0 = date bug) |
| `event_catalog` | ~495 |
| max `dancer_id` | 28,387+ |

## Branch model

- **`main`**: parser CSV + export CSV + pipeline code (Tableau reads this)
- **`old-laptop-version`**: temporary parser snapshots; merge via `build_merged_load_dataset.py`

## Validation gates

```bash
pytest tests/test_normalize_results_dates.py tests/test_pipeline_validation.py -q
python scripts/validate_pipeline_inputs.py --data-dir ./data
```

## Related

- [../tableau/index.md](../tableau/index.md) — Tableau refresh
- [pipeline-runbook.md](pipeline-runbook.md)

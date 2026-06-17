# Data sync: lessons from June 2026 desync

Use this when switching machines, merging branches, or making `main` the single source of truth.

## What went wrong

Three copies of truth diverged:

| Source | Typical state | Risk |
|--------|---------------|------|
| **Supabase** | Updated by CI load even when git push failed | DB ahead of repo |
| **`main` / GitHub CSV** | Stale export (June 12–14) | Tableau/repo behind DB |
| **Old laptop branch** | Fresh parser CSV (June 17), no export tables | Different row counts + IDs |
| **GitHub cloud parse** | Raw API dates (`January 1997`), no ISO year/month | Load succeeds but `event_editions` empty |

CI run can **succeed through load + export** and still leave **GitHub CSV stale** if the commit step fails (`git push rejected — fetch first`).

## Golden rules

1. **Supabase is not automatically mirrored to git.** After every successful load, verify either CSV commit on `main` or run `export_only` and commit manually.

2. **Parser CSV ≠ export CSV.**
   - Parser: `dancer_role_info`, `dancers_points_info`, `dancers_results_info`, `location_info`, `events_wsdc`
   - Export (from DB): `event_catalog`, `event_editions`, `scheduled_events`
   Do not mix “old laptop parser-only push” with “main export-only” without merging.

3. **Cloud parse always needs preprocess before load.**
   `extract_api.py` writes `event_year_and_month` as `"Month Year"`. Without `normalize_results_dates()` in preprocess, `core.results.event_year` stays NULL and `event_editions` stays 0.

4. **Compare before reload**, not after:
   ```bash
   python scripts/compare_csv_snapshots.py --local-dir ./data
   ```
   Check: `max_dancer_id`, row counts, date format (`iso_yam` vs `month_year_yam`), dancer_id sets.

5. **Merged reload from multiple sources** (when machines diverged):
   ```bash
   python scripts/build_merged_load_dataset.py --output-dir data/merged_load
   python scripts/validate_pipeline_inputs.py --data-dir data/merged_load
   python scripts/preprocess_data.py --data-dir data/merged_load --source local
   python load.py --data-dir data/merged_load --source local
   python export.py
   ```
   Default merge: old-laptop parser base + missing dancers/locations from `main` + extra result rows from Supabase staging (if any).

6. **Machine switch checklist**
   - `git pull --rebase origin main`
   - Compare local `data/*.csv` to `main` (or run compare script against a branch ref)
   - One authoritative parse per week — avoid parallel full parses on two laptops
   - Push parser CSV **or** load to Supabase, not both unaware
   - After load: `export.py` → commit `data/*.csv` in one PR

7. **CI / pooler:** GitHub Actions must use Supabase **transaction pooler** (see `docs/GITHUB_ACTIONS.md`). Long `rebuild_event_catalog` may need `statement_timeout` (see `load.py`).

## Expected row counts (order of magnitude, June 2026)

| File | ~rows |
|------|-------|
| `dancer_role_info` | 27 150–27 160 |
| `dancers_points_info` | 50 500 |
| `dancers_results_info` | 193 800+ |
| `event_editions` | 2 100+ (0 = date bug) |
| `max dancer_id` | 28 387+ |

## Branch model for side machines

- **`main`**: parser CSV + export CSV + pipeline code (Tableau reads this)
- **`old-laptop-version`** (or similar): temporary parser snapshots; merge via `build_merged_load_dataset.py`, do not treat as long-lived second main

## Validation gates (run before load)

```bash
pytest tests/test_normalize_results_dates.py tests/test_pipeline_validation.py -q
python scripts/validate_pipeline_inputs.py --data-dir ./data
```

Fails if <99% of result rows have parseable event dates.

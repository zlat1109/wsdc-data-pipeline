# Quality monitoring

Two layers: preprocess quality reports (CSV) and post-load SQL checks (database).

## Preprocess report

`scripts/preprocess_data.py` writes `data/quality_reports/latest.json`:

| Section | Meaning |
|---------|---------|
| `before_processing` | Raw defects before normalization |
| `applied_normalizations` | Rules applied with row counts |
| `manual_review_required` | Open issues; `"is_new": true` needs decision |

Add fixes to knowledge maps / preprocess based on `manual_review_required`, not items already in `applied_normalizations`.

See [../transform/index.md](../transform/index.md).

### Manual run

```bash
python scripts/preprocess_data.py --data-dir data
python scripts/preprocess_data.py --data-dir data --dry-run
```

Legacy audit-only: `scripts/data_quality_audit.py` (prefer preprocess).

## Post-load SQL checks

`scripts/monitor_data_quality.py` — run after load (also in CI `full-parse.yml`):

| Check | Target | Meaning |
|-------|--------|---------|
| `results_null_location_id` | 0 | All results have location |
| `split_names_same_geo` | 0 | No same-geo duplicate event_ids per raw name |
| `noncanonical_divisions` | 0 | No All-Stars / Champions / Masters |
| `points_history_drift` | 0 | Open points history matches `core.dancer_points` |
| `roles_history_drift` | 0 | Open division history matches `core.dancer_roles` (sig function) |
| `names_history_drift` | 0 | Open name history matches `core.dancers.dancer_name` |

Exit code 1 if any check fails.

```bash
python scripts/monitor_data_quality.py
```

### Extended validation (regression battery)

`scripts/validate_supabase_quality.py` runs core checks plus extended checks mapped to historical fixes (city normalization, phantom ids, location orphans, catalog drift). **Warnings** do not fail the exit code; **errors** do.

```bash
python scripts/validate_supabase_quality.py
python scripts/validate_supabase_quality.py --json
python scripts/validate_supabase_quality.py --core-only   # same as monitor
```

Check definitions live in `db/quality_checks.py` (single source of truth for monitor + validate).

| Extended check | Historical problem |
|----------------|-------------------|
| `dancers_empty_name` | API returned blank name for dancer with results/points |
| `orphan_location_id` | resolve.py backfill / repair_results_location |
| `all_caps_cities` | CHICAGO, TOULOUSE, WILMINGTON DEL |
| `double_space_event_location` | `Moscow,  Russia` |
| `city_equals_country` | geocode defects (Singapore whitelisted) |
| `phantom_ids_not_merged` | 467 Swing&Snow, 486–488 Grand Nationals |
| `swing_snow_alias` | registry spelling duplicate |
| `catalog_duplicate_city_token` | BeeMAD `Madrid, Madrid, Spain` |

## Event split audit

```bash
python scripts/audit_event_splits.py --output-dir data/quality_reports
```

Output: `event_splits_<timestamp>.json`, `event_splits_latest.json`

Classifications: `merge_candidate`, `keep_separate`, `manual_review`

## CI integration

`full-parse.yml` runs `validate_supabase_quality.py` after load (writes `data/quality_reports/supabase_latest.json`). Exit code 1 on **error**-severity failures.

Telegram `#WSDC_Pipeline_Complete`: if Supabase checks or preprocess manual review need attention, message includes a **⚠️ Требует внимания** block with failed checks and open review items. Clean runs omit that block.

Telegram pipeline-complete message includes quality log summary when secrets configured.

## Related

- [repair-scripts.md](repair-scripts.md)
- [../architecture/scd2-history.md](../architecture/scd2-history.md)

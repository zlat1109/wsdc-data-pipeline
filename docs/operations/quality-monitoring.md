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

<!-- docs-sync:core-quality-checks -->
| Check | Target | Meaning |
|-------|--------|---------|
| `results_null_location_id` | 0 | Cloud parse drops location_id; resolve.py backfills from event_location. |
| `split_names_same_geo` | 0 | Same raw event name + same geo must not map to multiple event_id. |
| `noncanonical_divisions` | 0 | Legacy plural division labels from old parser/registry. |
| `points_history_drift` | 0 | SCD2 open row must match core.dancer_points snapshot. |
| `roles_history_drift` | 0 | SCD2 open role row must match core.dancer_roles divisions. |
| `names_history_drift` | 0 | SCD2 open name row must match core.dancers.dancer_name. |
<!-- /docs-sync:core-quality-checks -->

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

<!-- docs-sync:extended-quality-checks -->
| Extended check | Historical problem |
|----------------|-------------------|
| `dancers_empty_name` | Active dancers with results/points should have a display name. |
| `orphan_location_id` | results.location_id must exist in core.locations. |
| `orphan_event_id` | Every result event_id must exist in core.events. |
| `editions_null_location_id` | Event editions derive location from results mode location_id. |
| `all_caps_cities` | ALL CAPS city names (CHICAGO, TOULOUSE, WILMINGTON DEL). |
| `location_id_multiple_strings` | One location_id must not have conflicting event_location strings. |
| `city_equals_country` | city=country usually geocode bug; Singapore ids 159/244 whitelisted. |
| `double_space_event_location` | Double spaces in location strings (Moscow,  Russia). |
| `catalog_duplicate_city_token` | Duplicated city in typical_location (Madrid, Madrid, Spain). |
| `phantom_ids_not_merged` | Phantom registry ids must be merged/inactive (Swing&Snow, Grand Nationals). |
| `swing_snow_alias` | Swing&Snow spelling variant must alias to canonical event_id 215. |
| `catalog_with_editions_missing_typical_location` | Events with results must have typical_location in catalog. |
<!-- /docs-sync:extended-quality-checks -->

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

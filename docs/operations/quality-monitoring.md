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

See [../transform/index.md](../transform/index.md) and [../transform/geography.md](../transform/geography.md) for location-collision handling.

### Location findings in preprocess audit

`run_audit` / preprocess report flags (among others):

| Code | Severity | What to do |
|------|----------|------------|
| `EVENT_NAME_LOCATION_ID_COLLISION` | high | Same `event_name` has multiple `location_id`s. Triage: wrong shared id → `EVENT_NAME_LOCATION_OVERRIDES`; metro/series move → leave or year-aware logic |
| `EVENT_NAME_LOCATION_COUNTRY_CONFLICT` | high | Name implies country ≠ results location country |
| `SCHEDULED_VS_RESULTS_COUNTRY_CONFLICT` | high | WSDC calendar country ≠ results location country |
| `EVENT_ID_CANONICAL_LOCATION_MISMATCH` | high | Results/editions country ≠ curated `event_id` canon (KNOWN / name override / upcoming). Catches uniform shared-wrong ids |
| `EDITION_LOCATION_BASELINE_DRIFT` | high | Results `location_id` for a known `(event_id, year, month)` differs from `edition_location_baseline.csv` (cross-load drift). Does not block load |
| `BASELINE_VS_LOCATION_OVERRIDE` | high | Baseline `location_id` disagrees with `EVENT_NAME_LOCATION_OVERRIDES` (poison seed / shared wrong lid frozen at seed). Does not block load |
| `CATALOG_TYPICAL_UPCOMING_CONFLICT` | medium | Catalog typical ≠ upcoming (stuck typical or real move) |

Quick offline scan (no full preprocess):

```bash
python -c "from pathlib import Path; from transform.quality_audit import load_csv_bundle, check_event_name_location_id_collision; d=load_csv_bundle(Path('data')); print(check_event_name_location_id_collision(d['dancers_results_info'], d.get('location_info')))"
```

### Manual run

```bash
python scripts/preprocess_data.py --data-dir data
python scripts/preprocess_data.py --data-dir data --dry-run
```

Legacy audit-only: `scripts/data_quality_audit.py` (prefer preprocess).

## Post-load SQL checks

`scripts/monitor_data_quality.py` — run after load (also in CI `full-parse.yml`):

**Completed-edition directory (Supabase):** `export.completed_event_editions` (materialized view, migration 032). Pre-flight location/id audits: `db/sql/audit_completed_event_location_links.sql`. Refresh after load: `SELECT export.refresh_completed_event_editions();`

**Edition location baseline (Supabase):** `core.edition_location_baseline` (migration 033) stores frozen `(event_id, event_year, event_month) → location_id`. Export: `export.edition_location_baseline` → `data/edition_location_baseline.csv`. After each load, `load.py` compares `core.event_editions` to baseline, auto-adds new edition keys, always refreshes `data/quality_reports/edition_location_baseline_drift.json` (`drift_count: 0` on clean runs). **First cycle after deploy:** migration 033 + export must run before preprocess CSV check is active; until then only post-load drift applies. Legitimate venue changes: `UPDATE core.edition_location_baseline SET location_id = …, source = 'manual', updated_at = now() WHERE …` in Supabase UI.

**Limitation (poison seed):** cross-load drift only fires when *current* ≠ baseline. If seed/auto-add froze an already-wrong shared `location_id` (e.g. St. Pete stuck on Perth), both stay equal and drift stays silent. Preprocess emits `BASELINE_VS_LOCATION_OVERRIDE` when baseline disagrees with `EVENT_NAME_LOCATION_OVERRIDES`. Schedule-vs-results (`SCHEDULED_VS_RESULTS_COUNTRY_CONFLICT`) is the other early signal for those cases.

<!-- docs-sync:core-quality-checks -->
| Check | Target | Meaning |
|-------|--------|---------|
| `results_null_location_id` | 0 | Cloud parse drops location_id; resolve.py backfills from event_location. |
| `split_names_same_geo` | 0 | Same raw event name + same geo must not map to multiple event_id. KEEP_SEPARATE pairs must keep distinct cities (use EVENT_NAME_YEAR_LOCATION_OVERRIDES for relocating series). |
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

**Duplicate results / bloated locations** are not separate SQL checks (exact duplicates do not break invariants). Detect via reconciliation or row counts, then repair with [repair-scripts.md](repair-scripts.md#dedupe_core_datapy) (`dedupe_core_data.py`) without a full parse. After PR #14, preprocess prevents new duplicates on load.

<!-- docs-sync:extended-quality-checks -->
| Extended check | Description |
|----------------|-------------|
| `dancers_empty_name` | Active dancers with results/points should have a display name. |
| `orphan_location_id` | results.location_id must exist in core.locations. |
| `orphan_event_id` | Every result event_id must exist in core.events. |
| `location_string_multiple_ids` | One location string must not map to multiple location_id values. |
| `edition_calendar_archive_empty` | Durable WSDC calendar dates archive should not be empty after load. |
| `edition_calendar_orphan_event_ids` | Calendar date rows must point at a current catalog event_id. |
| `events_list_current_empty` | Upcoming WSDC list snapshot should not be empty after load. |
| `schedule_orphan_location_id` | events_list_current.location_id must exist in core.locations (no FK). |
| `recent_editions_missing_day_dates` | Most 2025+ editions with results should have calendar day dates. |
| `editions_null_location_id` | Event editions derive location from results mode location_id. |
| `all_caps_cities` | ALL CAPS city names (CHICAGO, TOULOUSE, WILMINGTON DEL). |
| `location_id_multiple_strings` | One location_id must not have conflicting event_location strings. |
| `events_wsdc_edition_location_drift` | event_editions.location_raw disagrees with joined core.locations text. |
| `source_vs_results_location_conflicts_recent` | Source-derived edition location differs from results majority location_id (recent years). |
| `edition_location_baseline_drift` | Known edition key location_id differs from core.edition_location_baseline (cross-load drift — manual review) |
| `city_equals_country` | city=country usually geocode bug; city-states (Singapore) allowed. |
| `double_space_event_location` | Double spaces in location strings (Moscow,  Russia). |
| `catalog_duplicate_city_token` | Duplicated city in typical_location (Madrid, Madrid, Spain). |
| `phantom_ids_not_merged` | Phantom registry ids must be merged/inactive (MADjam, UK WCS, Grand Nationals, Kazan). |
| `phantom_aliases_point_to_expected_canonicals` | Phantom name aliases must point at the live canonical event_id. |
| `swing_snow_alias` | Swing&Snow spelling variant must alias to canonical event_id 215. |
| `catalog_with_editions_missing_typical_location` | Events with results must have typical_location in catalog. |
| `non_us_event_state` | event_state is only valid for United States locations. |
| `tier_unmatched_groups` | Post-2007 scored groups with ≥3 placements should resolve to a Chart 5 Tier. |
| `tier_range_conflicts` | scored_dancers exceeding rule_max_competitors is rare (data or chart mismatch). |
| `tier_missing_rules_version` | Groups from 2002+ must resolve to a rules_version. |
| `tier_rules_missing_finalist_points` | tier_points must include placement=0 (additional finalist) rows. |
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

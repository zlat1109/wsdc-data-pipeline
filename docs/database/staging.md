# Staging schema

Parser CSV files land in `staging.*` before normalization in load SQL. All columns are **text**; casting happens during promote.

**Lifecycle:** truncated and reloaded on every `load.py` run via `staging_loader.load_staging_from_dir`.

## staging.dancers_points_info

**Grain:** one points row per `(dancer_id, role, dance, level)` in parser output.

**Source CSV:** `dancers_points_info.csv`

| Column | Type | Description |
|--------|------|-------------|
| dancer_id | text | WSDC dancer registry id |
| role | text | `leader` / `follower` (normalized in preprocess) |
| dance | text | Dance code (e.g. WCS) |
| level | text | Division level (abbrev or full word) |
| total_points | text | Integer points total |
| update_date | text | Last update date from API |

## staging.dancer_role_info

**Grain:** one role-summary row per dancer.

**Source CSV:** `dancer_role_info.csv`

| Column | Type | Description |
|--------|------|-------------|
| dancer_id | text | WSDC dancer id |
| dancer_name | text | Display name |
| dominate_role | text | Primary role |
| dominate_required | text | Required level (dominate role) |
| dominate_allowed | text | Allowed levels |
| non_dominate_role | text | Secondary role |
| non_dominate_required | text | Required level (non-dominate) |
| non_dominate_allowed | text | Allowed levels |
| non_dominate_recommended | text | Recommended level |
| non_dominate_role_highest_level_points | text | Points at highest non-dom level |
| non_dominate_role_highest_level | text | Highest non-dominate level |
| update_date | text | Snapshot date |

## staging.dancers_results_info

**Grain:** one competition result row.

**Source CSV:** `dancers_results_info.csv`

| Column | Type | Description |
|--------|------|-------------|
| dancer_id | text | Dancer id |
| event_dance | text | Dance |
| event_competition | text | Division / level (→ `core.results.division`) |
| event_role | text | Role in this result |
| event_name_id | text | Legacy event id column (parser variant) |
| event_name | text | Event title (→ alias resolution) |
| event_result | text | Placement raw (`1`..`5`, `F`, etc.) |
| event_points | text | Points earned |
| event_month | text | Month (after preprocess: integer string) |
| event_year | text | Year |
| location_id | text | FK to location_info |
| event_year_and_month | text | ISO date or `"Month Year"` before preprocess |
| event_result_standardized | text | Normalized placement |

## staging.location_info

**Grain:** one location registry row.

**Source CSV:** `location_info.csv`

| Column | Type | Description |
|--------|------|-------------|
| location_id | text | WSDC location id |
| event_city | text | City |
| event_state | text | State / region |
| event_country | text | Country |
| latitude | text | Decimal degrees |
| longitude | text | Decimal degrees |
| event_location | text | Display label |
| event_location_standardized | text | Normalized label |
| coordinates_valid | text | Boolean string |

## staging.events_wsdc

**Grain:** one event registry instance row (historical listing from WSDC).

**Source CSV:** `events_wsdc.csv`

| Column | Type | Description |
|--------|------|-------------|
| event_instance_id | text | Instance surrogate |
| id | text | WSDC `event_id` |
| name | text | Official registry name |
| location | text | Raw location string |
| url | text | Event URL |
| date | text | Raw date label |
| parsed_date | text | Parsed date |
| event_year | text | Year |
| event_month | text | Month |
| event_year_month | text | Combined date field |

## staging.changed_dancers_points_info

**Grain:** one historical points change row (backfill source).

**Source CSV:** `changed_dancer_points_info.csv` (legacy accumulated log)

Same columns as `staging.dancers_points_info`. Used during initial history backfill, not weekly load.

## staging.changed_dancer_role_info

**Grain:** one historical role-summary snapshot row (legacy accumulated log).

**Source CSV:** `changed_dancer_role_info.csv`

Same columns as `staging.dancer_role_info`. Used for **initial** history backfill only (`backfill.py` / `split_legacy_role_history.py`), not weekly load.

On backfill, pandas splits this file into:

- `history.dancer_roles_history` — division changes (`core.dancer_roles_division_sig`)
- `history.dancer_names_history` — display name changes

Weekly load records both tracks from current `staging.dancer_role_info` via `record_weekly_roles_history.sql` and `record_weekly_names_history.sql`.

## CSV → staging mapping

Loader reads filenames from `data/` (or `--data-dir`) and bulk-copies into matching staging tables. Column order must match parser contract — validated by `scripts/validate_pipeline_inputs.py`.

## Related

- [core.md](core.md) — promote targets
- [../transform/index.md](../transform/index.md) — preprocess before load

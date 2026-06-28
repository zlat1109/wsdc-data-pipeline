# History schema

Run journal and SCD2 change tables. Append-only semantics for history rows (close intervals, do not delete versions).

## history.parse_runs

**Grain:** one pipeline or probe execution.

**Primary key:** `run_id` (identity)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| run_id | bigint | NO | Surrogate PK |
| started_at | timestamptz | NO | Run start |
| finished_at | timestamptz | YES | Run end |
| source | text | NO | `github-actions`, `local`, `backfill` |
| probe_hash | text | YES | Update-check fingerprint |
| rows_results | int | YES | Results loaded |
| rows_points | int | YES | Points rows |
| points_changed | int | YES | History changes recorded |
| dancers_added | int | YES | New dancers |
| status | text | NO | `running`, `success`, `failed`, `skipped` |

Extended in migration 006 for watermark probe fields (`max_dancer_id_watermark`, etc.).

## history.dancer_points_history

**Grain:** one points total valid during `[valid_from, valid_to]`.

**Primary key:** `(dancer_id, role, dance, level, valid_from)`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| dancer_id | int | NO | Dancer |
| role | text | NO | Leader / Follower |
| dance | text | NO | Dance code |
| level | text | NO | Level name |
| total_points | int | NO | Points during interval |
| valid_from | date | NO | Interval start |
| valid_to | date | YES | Interval end; NULL = open |
| run_id | bigint | YES | FK → `parse_runs` |

**Index:** partial on `valid_to IS NULL` for current-version lookups.

## history.dancer_roles_history

**Grain:** one role-summary snapshot valid during `[valid_from, valid_to]`.

**Primary key:** `(dancer_id, valid_from)`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| dancer_id | int | NO | Dancer |
| dancer_name | text | YES | Denormalized snapshot (not a change trigger) |
| dominate_role | text | YES | Primary role |
| dominate_required | text | YES | Required level |
| dominate_allowed | text | YES | Allowed |
| non_dominate_role | text | YES | Secondary role |
| non_dominate_required | text | YES | Required |
| non_dominate_allowed | text | YES | Allowed |
| non_dominate_recommended | text | YES | Recommended |
| non_dominate_role_highest_level_points | text | YES | Points |
| non_dominate_role_highest_level | text | YES | Level |
| valid_from | date | NO | Interval start |
| valid_to | date | YES | Interval end; NULL = open |
| run_id | bigint | YES | FK → `parse_runs` |

## history.dancer_names_history

**Grain:** one display-name version valid during `[valid_from, valid_to]`.

**Primary key:** `(dancer_id, valid_from)`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| dancer_id | int | NO | Dancer |
| dancer_name | text | NO | Display name during interval |
| valid_from | date | NO | Interval start |
| valid_to | date | YES | Interval end; NULL = open |
| run_id | bigint | YES | FK → `parse_runs` |

## history.events_list_runs

**Grain:** one WSDC events page scrape run.

**Primary key:** `run_id` (serial)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| run_id | int | NO | Run id |
| scraped_at | timestamptz | NO | Scrape timestamp |
| source | text | NO | Usually `github-actions` |
| total_events | int | NO | Events on page |
| added_count | int | NO | New vs previous |
| removed_count | int | NO | Removed vs previous |
| unchanged_count | int | NO | Unchanged |

## history.events_list_changes

**Grain:** one added or removed event per scrape run.

**Primary key:** `change_id` (identity)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| change_id | bigint | NO | Surrogate PK |
| run_id | int | NO | FK → `events_list_runs` |
| change_type | text | NO | `added` or `removed` |
| source_fingerprint | text | NO | Edition fingerprint |
| event_name | text | YES | Title |
| start_date | date | YES | Start |
| end_date | date | YES | End |
| location_raw | text | YES | Location |
| url | text | YES | URL |
| snapshot | jsonb | YES | Full row snapshot |

## Weekly SQL

| File | Purpose |
|------|---------|
| `db/sql/record_weekly_points_history.sql` | Close/insert points intervals |
| `db/sql/record_weekly_roles_history.sql` | Close/insert division intervals |
| `db/sql/record_weekly_names_history.sql` | Close/insert name intervals |

Run from `load.py` before `promote_core.sql`.

## Related

- [../architecture/scd2-history.md](../architecture/scd2-history.md) — semantics
- [../operations/repair-scripts.md](../operations/repair-scripts.md) — reconcile drift

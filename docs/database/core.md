# Core schema

Normalized **current state** after each successful load. Canonical formats use full words (`Leader`, `All-Star`) matching legacy Tableau CSVs.

## core.levels

**Grain:** one WSDC competition level.

**Primary key:** `level`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| level | text | NO | Canonical name (e.g. `All-Star`) |
| level_abbr | text | NO | Parser abbreviation (e.g. `ALS`) |
| sort_order | int | NO | Progression order for analytics |

Seeded in migration 003. Referenced by `core.dancer_points.level`.

## core.dancers

**Grain:** one registered dancer.

**Primary key:** `dancer_id`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| dancer_id | int | NO | WSDC registry id |
| dancer_name | text | YES | Current display name |

## core.locations

**Grain:** one WSDC location registry entry.

**Primary key:** `location_id`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| location_id | int | NO | WSDC location id |
| event_city | text | YES | City |
| event_state | text | YES | State / region |
| event_country | text | YES | Country |
| latitude | numeric | YES | WGS84 latitude |
| longitude | numeric | YES | WGS84 longitude |
| event_location | text | YES | Display string |
| event_location_standardized | text | YES | Normalized display |
| coordinates_valid | boolean | YES | Coords verified |

**Indexes:** used by results join; geography corrections in `transform/knowledge/locations.py`.

## core.events

**Grain:** one WSDC registry event (brand).

**Primary key:** `event_id`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| event_id | int | NO | WSDC registry number |
| name | text | NO | Official catalog title from registry |
| url | text | YES | Event website |

Do not rename for marketing rebrands — use `event_aliases` and `event_name_raw`.

## core.event_aliases

**Grain:** one known alternate title → registry id.

**Primary key:** `alias`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| alias | text | NO | Raw or marketing event name |
| event_id | int | NO | FK → `core.events` |

Seeded from preprocess maps and merge scripts.

## core.event_instances

**Grain:** one row from WSDC events registry export (historical instance listing).

**Primary key:** `event_instance_id`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| event_instance_id | int | NO | Instance id |
| event_id | int | YES | FK → `core.events` |
| location_id | int | YES | FK → `core.locations` |
| location_raw | text | YES | Raw location from registry |
| date_raw | text | YES | As published (`July 1991`) |
| event_date | date | YES | Parsed date |
| event_year | int | YES | Year |
| event_month | int | YES | Month |

Powers `export.events_wsdc` view.

## core.results

**Grain:** one competition result (dancer × event edition × dance × division × role).

**Primary key:** `result_id` (identity)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| result_id | bigint | NO | Surrogate PK |
| dancer_id | int | NO | FK → `core.dancers` |
| event_id | int | YES | FK → `core.events` |
| location_id | int | YES | FK → `core.locations` |
| dance | text | YES | Dance code |
| division | text | YES | Level / division (`event_competition`) |
| role | text | YES | `Leader` or `Follower` |
| event_year | int | YES | Edition year |
| event_month | int | YES | Edition month |
| event_date | date | YES | Edition date |
| result_raw | text | YES | Raw placement |
| result_standardized | text | YES | Normalized placement |
| points | int | YES | Points earned |
| event_name_raw | text | YES | Original API title (migration 016) |

**Indexes:** `results_dancer_idx`, `results_event_idx`, `results_location_idx`, `results_event_name_raw_idx`

**Join edition:** `(event_id, event_year, event_month)` → `core.event_editions`

## core.dancer_points

**Grain:** current points total for `(dancer_id, role, dance, level)`.

**Primary key:** `(dancer_id, role, dance, level)`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| dancer_id | int | NO | FK → `core.dancers` |
| role | text | NO | `Leader` / `Follower` |
| dance | text | NO | Dance code |
| level | text | NO | FK → `core.levels` |
| total_points | int | NO | Current total |
| update_date | date | YES | API update date |

Full snapshot replaced each load.

## core.dancer_roles

**Grain:** current role-summary row per dancer.

**Primary key:** `dancer_id`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| dancer_id | int | NO | FK → `core.dancers` |
| dominate_role | text | YES | Primary role |
| dominate_required | text | YES | Required level |
| dominate_allowed | text | YES | Allowed levels |
| non_dominate_role | text | YES | Secondary role |
| non_dominate_required | text | YES | Required level |
| non_dominate_allowed | text | YES | Allowed levels |
| non_dominate_recommended | text | YES | Recommended level |
| non_dominate_role_highest_level_points | text | YES | Points |
| non_dominate_role_highest_level | text | YES | Level name |
| update_date | date | YES | Snapshot date |

## core.event_catalog

**Grain:** one row per registry event (brand-level analytics).

**Primary key:** `event_id`

**Rebuild:** `db/build_event_catalog.py` after each load.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| event_id | int | NO | FK → `core.events` |
| canonical_name | text | NO | Display name for dashboards |
| url | text | YES | Event URL |
| registry_status | text | YES | `active`, `inactive`, `merged`, etc. |
| typical_city | text | YES | Mode city from results |
| typical_state | text | YES | Mode state |
| typical_country | text | YES | Mode country |
| typical_location | text | YES | Combined label |
| first_edition_year | int | YES | Earliest edition |
| last_edition_year | int | YES | Latest edition |
| edition_count | int | NO | Distinct editions |
| total_result_rows | bigint | NO | Result count |
| unique_dancers | int | NO | Distinct dancers |
| upcoming_start_date | date | YES | From schedule link |
| upcoming_location | text | YES | From schedule |
| updated_at | timestamptz | NO | Last rebuild time |

## core.event_editions

**Grain:** one event held in a given year and month.

**Primary key:** `edition_id` (identity)

**Unique:** `(event_id, event_year, event_month)`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| edition_id | bigint | NO | Surrogate PK |
| event_id | int | NO | FK → `core.events` |
| event_year | int | NO | Edition year |
| event_month | int | NO | Edition month |
| edition_date | date | YES | Parsed edition date |
| location_id | int | YES | FK → `core.locations` |
| place_city | text | YES | Edition city |
| place_state | text | YES | Edition state |
| place_country | text | YES | Edition country |
| location_raw | text | YES | Raw location string |
| result_rows | int | NO | Results in this edition |
| unique_dancers | int | NO | Distinct dancers |

## core.scheduled_events

**Grain:** one scraped edition observation (archive of all fingerprints seen on WSDC events page).

**Primary key:** `source_fingerprint`

Updated by `scripts/sync_events_list.py`. Not truncated by points load.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| source_fingerprint | text | NO | Stable hash of scrape row |
| event_name | text | NO | Title on WSDC site |
| original_date | text | YES | Date string from site |
| start_date | date | YES | Parsed start |
| end_date | date | YES | Parsed end |
| results_year | int | YES | Results attribution year |
| results_month | int | YES | Results attribution month |
| location_raw | text | YES | Location on site |
| country | text | YES | Country |
| country_flag | text | YES | Flag emoji / code |
| url | text | YES | Event URL |
| status_event | text | YES | Registry / trial status |
| confirmed | boolean | YES | Confirmed flag |
| canceled | boolean | YES | Canceled |
| on_hiatus | boolean | YES | Hiatus |
| is_active | boolean | YES | Still on site |
| first_seen_at | timestamptz | NO | First scrape |
| last_seen_at | timestamptz | NO | Last scrape |
| last_run_id | int | YES | FK → `history.events_list_runs` |

## core.events_list_current

**Grain:** one logical upcoming event (nearest edition per brand).

**Primary key:** `schedule_event_key`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| schedule_event_key | text | NO | Stable schedule key |
| source_fingerprint | text | NO | Current edition fingerprint |
| canonical_event_id | int | YES | Matched `core.events.event_id` |
| event_name | text | NO | Name on WSDC site |
| canonical_name | text | YES | Matched catalog name |
| original_date | text | YES | Date string |
| start_date | date | YES | Start date |
| end_date | date | YES | End date |
| results_year | int | YES | Results year |
| results_month | int | YES | Results month |
| location_raw | text | YES | Location |
| country | text | YES | Country |
| country_flag | text | YES | Flag |
| url | text | YES | URL |
| status_event | text | YES | Status |
| confirmed | boolean | YES | Confirmed |
| canceled | boolean | YES | Canceled |
| on_hiatus | boolean | YES | Hiatus |
| match_status | text | YES | Mapping status |
| match_method | text | YES | How match was made |
| match_confidence | double precision | YES | Match score |
| upcoming_editions | int | NO | Count of future editions |
| updated_at | timestamptz | NO | Last sync |
| last_run_id | int | YES | FK → `history.events_list_runs` |

Powers `export.scheduled_events`.

## Related

- [history.md](history.md) — change log
- [export-views.md](export-views.md) — Tableau views
- [../architecture/identity-model.md](../architecture/identity-model.md)

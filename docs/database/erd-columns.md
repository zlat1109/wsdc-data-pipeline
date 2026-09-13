# Full column inventory

Source: `db/migrations/*.sql` (DDL applied to Supabase).
Tables: **26**. Interactive map: [full ERD explorer](../assets/erd-explorer-full.html).
Compact map (keys only): [ERD explorer](../assets/erd-explorer.html).
Regenerate: `python scripts/generate_erd_full.py`.

## `core.levels`

| Column | Type | Keys |
|--------|------|------|
| `level` | `text` | PK |
| `level_abbr` | `text` | — |
| `sort_order` | `int` | — |

## `core.dancers`

| Column | Type | Keys |
|--------|------|------|
| `dancer_id` | `int` | PK |
| `dancer_name` | `text` | — |

## `core.locations`

| Column | Type | Keys |
|--------|------|------|
| `location_id` | `int` | PK |
| `event_city` | `text` | — |
| `event_state` | `text` | — |
| `event_country` | `text` | — |
| `latitude` | `numeric` | — |
| `longitude` | `numeric` | — |
| `event_location` | `text` | — |
| `event_location_standardized` | `text` | — |
| `coordinates_valid` | `bool` | — |

## `core.events`

| Column | Type | Keys |
|--------|------|------|
| `event_id` | `int` | PK |
| `name` | `text` | — |
| `url` | `text` | — |

## `core.event_aliases`

| Column | Type | Keys |
|--------|------|------|
| `alias` | `text` | PK |
| `event_id` | `int` | FK |

## `core.event_instances`

| Column | Type | Keys |
|--------|------|------|
| `event_instance_id` | `int` | PK |
| `event_id` | `int` | FK |
| `location_id` | `int` | FK |
| `location_raw` | `text` | — |
| `date_raw` | `text` | — |
| `event_date` | `date` | — |
| `event_year` | `int` | — |
| `event_month` | `int` | — |

## `core.results`

| Column | Type | Keys |
|--------|------|------|
| `result_id` | `bigint` | PK |
| `dancer_id` | `int` | FK |
| `event_id` | `int` | FK |
| `location_id` | `int` | FK |
| `dance` | `text` | — |
| `division` | `text` | — |
| `role` | `text` | — |
| `event_year` | `int` | — |
| `event_month` | `int` | — |
| `event_date` | `date` | — |
| `result_raw` | `text` | — |
| `result_standardized` | `text` | — |
| `points` | `int` | — |
| `event_name_raw` | `text` | — |

## `core.dancer_points`

| Column | Type | Keys |
|--------|------|------|
| `dancer_id` | `int` | PK, FK |
| `role` | `text` | PK |
| `dance` | `text` | PK |
| `level` | `text` | PK, FK |
| `total_points` | `int` | — |
| `update_date` | `date` | — |

## `core.dancer_roles`

| Column | Type | Keys |
|--------|------|------|
| `dancer_id` | `int` | PK, FK |
| `dominate_role` | `text` | — |
| `dominate_required` | `text` | — |
| `dominate_allowed` | `text` | — |
| `non_dominate_role` | `text` | — |
| `non_dominate_required` | `text` | — |
| `non_dominate_allowed` | `text` | — |
| `non_dominate_recommended` | `text` | — |
| `non_dominate_role_highest_level_points` | `text` | — |
| `non_dominate_role_highest_level` | `text` | — |
| `update_date` | `date` | — |

## `history.parse_runs`

| Column | Type | Keys |
|--------|------|------|
| `run_id` | `bigint` | PK |
| `started_at` | `timestamptz` | — |
| `finished_at` | `timestamptz` | — |
| `source` | `text` | — |
| `probe_hash` | `text` | — |
| `rows_results` | `int` | — |
| `rows_points` | `int` | — |
| `points_changed` | `int` | — |
| `dancers_added` | `int` | — |
| `status` | `text` | — |
| `max_dancer_id_watermark` | `int` | — |
| `new_dancer_ids` | `jsonb` | — |
| `probe_details` | `jsonb` | — |

## `history.dancer_points_history`

| Column | Type | Keys |
|--------|------|------|
| `dancer_id` | `int` | PK |
| `role` | `text` | PK |
| `dance` | `text` | PK |
| `level` | `text` | PK |
| `total_points` | `int` | — |
| `valid_from` | `date` | PK |
| `valid_to` | `date` | — |
| `run_id` | `bigint` | FK |

## `history.dancer_roles_history`

| Column | Type | Keys |
|--------|------|------|
| `dancer_id` | `int` | PK |
| `dancer_name` | `text` | — |
| `dominate_role` | `text` | — |
| `dominate_required` | `text` | — |
| `dominate_allowed` | `text` | — |
| `non_dominate_role` | `text` | — |
| `non_dominate_required` | `text` | — |
| `non_dominate_allowed` | `text` | — |
| `non_dominate_recommended` | `text` | — |
| `non_dominate_role_highest_level_points` | `text` | — |
| `non_dominate_role_highest_level` | `text` | — |
| `valid_from` | `date` | PK |
| `valid_to` | `date` | — |
| `run_id` | `bigint` | FK |

## `history.events_list_runs`

| Column | Type | Keys |
|--------|------|------|
| `run_id` | `int` | PK |
| `scraped_at` | `timestamptz` | — |
| `source` | `text` | — |
| `total_events` | `int` | — |
| `added_count` | `int` | — |
| `removed_count` | `int` | — |
| `unchanged_count` | `int` | — |

## `core.scheduled_events`

| Column | Type | Keys |
|--------|------|------|
| `source_fingerprint` | `text` | PK |
| `event_name` | `text` | — |
| `original_date` | `text` | — |
| `start_date` | `date` | — |
| `end_date` | `date` | — |
| `results_year` | `int` | — |
| `results_month` | `int` | — |
| `location_raw` | `text` | — |
| `country` | `text` | — |
| `country_flag` | `text` | — |
| `url` | `text` | — |
| `status_event` | `text` | — |
| `confirmed` | `bool` | — |
| `canceled` | `bool` | — |
| `on_hiatus` | `bool` | — |
| `is_active` | `bool` | — |
| `first_seen_at` | `timestamptz` | — |
| `last_seen_at` | `timestamptz` | — |
| `last_run_id` | `int` | FK |
| `location_id` | `int` | — |
| `location_source` | `text` | — |

## `history.events_list_changes`

| Column | Type | Keys |
|--------|------|------|
| `change_id` | `bigint` | PK |
| `run_id` | `int` | FK |
| `change_type` | `text` | — |
| `source_fingerprint` | `text` | — |
| `event_name` | `text` | — |
| `start_date` | `date` | — |
| `end_date` | `date` | — |
| `location_raw` | `text` | — |
| `url` | `text` | — |
| `snapshot` | `jsonb` | — |

## `core.events_list_current`

| Column | Type | Keys |
|--------|------|------|
| `schedule_event_key` | `text` | PK |
| `source_fingerprint` | `text` | — |
| `canonical_event_id` | `int` | — |
| `event_name` | `text` | — |
| `canonical_name` | `text` | — |
| `original_date` | `text` | — |
| `start_date` | `date` | — |
| `end_date` | `date` | — |
| `results_year` | `int` | — |
| `results_month` | `int` | — |
| `location_raw` | `text` | — |
| `country` | `text` | — |
| `country_flag` | `text` | — |
| `url` | `text` | — |
| `status_event` | `text` | — |
| `confirmed` | `bool` | — |
| `canceled` | `bool` | — |
| `on_hiatus` | `bool` | — |
| `match_status` | `text` | — |
| `match_method` | `text` | — |
| `match_confidence` | `float` | — |
| `upcoming_editions` | `int` | — |
| `updated_at` | `timestamptz` | — |
| `last_run_id` | `int` | FK |
| `location_id` | `int` | — |
| `location_source` | `text` | — |

## `core.event_catalog`

| Column | Type | Keys |
|--------|------|------|
| `event_id` | `int` | PK, FK |
| `canonical_name` | `text` | — |
| `url` | `text` | — |
| `registry_status` | `text` | — |
| `typical_city` | `text` | — |
| `typical_state` | `text` | — |
| `typical_country` | `text` | — |
| `typical_location` | `text` | — |
| `first_edition_year` | `int` | — |
| `last_edition_year` | `int` | — |
| `edition_count` | `int` | — |
| `total_result_rows` | `bigint` | — |
| `upcoming_start_date` | `date` | — |
| `upcoming_location` | `text` | — |
| `updated_at` | `timestamptz` | — |

## `core.event_editions`

| Column | Type | Keys |
|--------|------|------|
| `edition_id` | `bigint` | PK |
| `event_id` | `int` | FK |
| `event_year` | `int` | — |
| `event_month` | `int` | — |
| `edition_date` | `date` | — |
| `location_id` | `int` | FK |
| `place_city` | `text` | — |
| `place_state` | `text` | — |
| `place_country` | `text` | — |
| `location_raw` | `text` | — |
| `result_rows` | `int` | — |
| `start_date` | `date` | — |
| `end_date` | `date` | — |
| `date_source` | `text` | — |
| `calendar_status` | `text` | — |
| `event_occurred` | `bool` | — |

## `history.dancer_names_history`

| Column | Type | Keys |
|--------|------|------|
| `dancer_id` | `int` | PK |
| `dancer_name` | `text` | — |
| `valid_from` | `date` | PK |
| `valid_to` | `date` | — |
| `run_id` | `bigint` | FK |

## `core.dancer_aliases`

| Column | Type | Keys |
|--------|------|------|
| `alias` | `text` | PK |
| `dancer_id` | `int` | FK |
| `source` | `text` | — |
| `notes` | `text` | — |

## `core.edition_calendar_dates`

| Column | Type | Keys |
|--------|------|------|
| `event_id` | `int` | PK |
| `event_year` | `int` | PK |
| `event_month` | `int` | PK |
| `planned_start_date` | `date` | — |
| `planned_end_date` | `date` | — |
| `calendar_status` | `text` | — |
| `date_source` | `text` | — |
| `source_fingerprint` | `text` | — |
| `calendar_title` | `text` | — |
| `url` | `text` | — |
| `match_via` | `text` | — |
| `scraped_at` | `timestamptz` | — |
| `updated_at` | `timestamptz` | — |

## `core.rules_editions`

| Column | Type | Keys |
|--------|------|------|
| `rules_version` | `text` | PK |
| `valid_from` | `date` | — |
| `valid_to` | `date` | — |
| `tier_basis` | `text` | — |
| `min_role_competitors` | `int` | — |
| `points_depth` | `int` | — |
| `inherits_from` | `text` | FK |
| `source_url` | `text` | — |
| `source` | `text` | — |
| `notes` | `text` | — |
| `updated_at` | `timestamptz` | — |

## `core.tier_definitions`

| Column | Type | Keys |
|--------|------|------|
| `rules_version` | `text` | PK, FK |
| `tier` | `int` | PK |
| `min_competitors` | `int` | — |
| `max_competitors` | `int` | — |
| `prelim_rounds` | `int` | — |
| `finalist_points` | `int` | — |
| `source` | `text` | — |
| `finalist_max_place` | `int` | — |

## `core.tier_points`

| Column | Type | Keys |
|--------|------|------|
| `rules_version` | `text` | PK |
| `tier` | `int` | PK |
| `placement` | `int` | PK |
| `points` | `int` | — |
| `source` | `text` | — |
| `REFERENCES` | `core` | — |

## `core.edition_division_tiers`

| Column | Type | Keys |
|--------|------|------|
| `event_id` | `int` | PK |
| `event_year` | `int` | PK |
| `event_month` | `int` | PK |
| `division` | `text` | PK |
| `role` | `text` | PK |
| `dance` | `text` | PK |
| `edition_id` | `bigint` | — |
| `rules_version` | `text` | — |
| `observed_points_1` | `int` | — |
| `observed_points_2` | `int` | — |
| `observed_points_3` | `int` | — |
| `observed_points_4` | `int` | — |
| `observed_points_5` | `int` | — |
| `finalists` | `int` | — |
| `scored_dancers` | `int` | — |
| `tier` | `int` | — |
| `status` | `text` | — |
| `vector_distance` | `int` | — |
| `range_basis` | `text` | — |
| `rule_min_competitors` | `int` | — |
| `rule_max_competitors` | `int` | — |
| `est_min_competitors` | `int` | — |
| `est_max_competitors` | `int` | — |
| `range_conflict` | `bool` | — |
| `updated_at` | `timestamptz` | — |

## `core.edition_location_baseline`

| Column | Type | Keys |
|--------|------|------|
| `event_id` | `int` | PK, FK |
| `event_year` | `int` | PK |
| `event_month` | `int` | PK |
| `location_id` | `int` | FK |
| `event_name` | `text` | — |
| `source` | `text` | — |
| `seeded_at` | `timestamptz` | — |
| `updated_at` | `timestamptz` | — |

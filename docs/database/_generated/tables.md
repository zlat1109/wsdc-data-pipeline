# Generated tables

[auto] Regenerate with `python scripts/generate_schema_docs.py`

## core.dancer_points
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| dancer_id | text/PK/FK | integer |
| role | text/PK/FK | text |
| dance | text/PK/FK | text |
| level | text/PK/FK | text |
| total_points | text/PK/FK | integer |
| update_date | text/PK/FK | date |

## core.dancer_roles
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| dancer_id | text/PK/FK | integer |
| dominate_role | text/PK/FK | text |
| dominate_required | text/PK/FK | text |
| dominate_allowed | text/PK/FK | text |
| non_dominate_role | text/PK/FK | text |
| non_dominate_required | text/PK/FK | text |
| non_dominate_allowed | text/PK/FK | text |
| non_dominate_recommended | text/PK/FK | text |
| non_dominate_role_highest_level_points | text/PK/FK | text |
| non_dominate_role_highest_level | text/PK/FK | text |
| update_date | text/PK/FK | date |

## core.dancers
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| dancer_id | text/PK/FK | integer |
| dancer_name | text/PK/FK | text |

## core.event_aliases
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| alias | text/PK/FK | text |
| event_id | text/PK/FK | integer |

## core.event_catalog

One row per WSDC registry event (brand): URL, typical location, edition stats.

| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| event_id | text/PK/FK | integer |
| canonical_name | text/PK/FK | text |
| url | text/PK/FK | text |
| registry_status | text/PK/FK | text |
| typical_city | text/PK/FK | text |
| typical_state | text/PK/FK | text |
| typical_country | text/PK/FK | text |
| typical_location | text/PK/FK | text |
| first_edition_year | text/PK/FK | integer |
| last_edition_year | text/PK/FK | integer |
| edition_count | text/PK/FK | integer |
| total_result_rows | text/PK/FK | bigint |
| upcoming_start_date | text/PK/FK | date |
| upcoming_location | text/PK/FK | text |
| updated_at | text/PK/FK | timestamp with time zone |

## core.event_editions

One row per event held in a given year/month; join results on (event_id, event_year, event_month).

| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| edition_id | text/PK/FK | bigint |
| event_id | text/PK/FK | integer |
| event_year | text/PK/FK | integer |
| event_month | text/PK/FK | integer |
| edition_date | text/PK/FK | date |
| location_id | text/PK/FK | integer |
| place_city | text/PK/FK | text |
| place_state | text/PK/FK | text |
| place_country | text/PK/FK | text |
| location_raw | text/PK/FK | text |
| result_rows | text/PK/FK | integer |

## core.event_instances
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| event_instance_id | text/PK/FK | integer |
| event_id | text/PK/FK | integer |
| location_id | text/PK/FK | integer |
| location_raw | text/PK/FK | text |
| date_raw | text/PK/FK | text |
| event_date | text/PK/FK | date |
| event_year | text/PK/FK | integer |
| event_month | text/PK/FK | integer |

## core.events
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| event_id | text/PK/FK | integer |
| name | text/PK/FK | text |
| url | text/PK/FK | text |

## core.events_list_current

Latest schedule snapshot: one row per logical event (nearest upcoming edition).

| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| schedule_event_key | text/PK/FK | text |
| source_fingerprint | text/PK/FK | text |
| canonical_event_id | text/PK/FK | integer |
| event_name | text/PK/FK | text |
| canonical_name | text/PK/FK | text |
| original_date | text/PK/FK | text |
| start_date | text/PK/FK | date |
| end_date | text/PK/FK | date |
| results_year | text/PK/FK | integer |
| results_month | text/PK/FK | integer |
| location_raw | text/PK/FK | text |
| country | text/PK/FK | text |
| country_flag | text/PK/FK | text |
| url | text/PK/FK | text |
| status_event | text/PK/FK | text |
| confirmed | text/PK/FK | boolean |
| canceled | text/PK/FK | boolean |
| on_hiatus | text/PK/FK | boolean |
| match_status | text/PK/FK | text |
| match_method | text/PK/FK | text |
| match_confidence | text/PK/FK | double precision |
| upcoming_editions | text/PK/FK | integer |
| updated_at | text/PK/FK | timestamp with time zone |
| last_run_id | text/PK/FK | integer |

## core.levels
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| level | text/PK/FK | text |
| level_abbr | text/PK/FK | text |
| sort_order | text/PK/FK | integer |

## core.locations
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| location_id | text/PK/FK | integer |
| event_city | text/PK/FK | text |
| event_state | text/PK/FK | text |
| event_country | text/PK/FK | text |
| latitude | text/PK/FK | numeric |
| longitude | text/PK/FK | numeric |
| event_location | text/PK/FK | text |
| event_location_standardized | text/PK/FK | text |
| coordinates_valid | text/PK/FK | boolean |

## core.results
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| result_id | text/PK/FK | bigint |
| dancer_id | text/PK/FK | integer |
| event_id | text/PK/FK | integer |
| location_id | text/PK/FK | integer |
| dance | text/PK/FK | text |
| division | text/PK/FK | text |
| role | text/PK/FK | text |
| event_year | text/PK/FK | integer |
| event_month | text/PK/FK | integer |
| event_date | text/PK/FK | date |
| result_raw | text/PK/FK | text |
| result_standardized | text/PK/FK | text |
| points | text/PK/FK | integer |

## core.scheduled_events

Edition-level schedule archive keyed by source_fingerprint (all scrape observations).

| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| source_fingerprint | text/PK/FK | text |
| event_name | text/PK/FK | text |
| original_date | text/PK/FK | text |
| start_date | text/PK/FK | date |
| end_date | text/PK/FK | date |
| results_year | text/PK/FK | integer |
| results_month | text/PK/FK | integer |
| location_raw | text/PK/FK | text |
| country | text/PK/FK | text |
| country_flag | text/PK/FK | text |
| url | text/PK/FK | text |
| status_event | text/PK/FK | text |
| confirmed | text/PK/FK | boolean |
| canceled | text/PK/FK | boolean |
| on_hiatus | text/PK/FK | boolean |
| is_active | text/PK/FK | boolean |
| first_seen_at | text/PK/FK | timestamp with time zone |
| last_seen_at | text/PK/FK | timestamp with time zone |
| last_run_id | text/PK/FK | integer |

## history.dancer_points_history
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| dancer_id | text/PK/FK | integer |
| role | text/PK/FK | text |
| dance | text/PK/FK | text |
| level | text/PK/FK | text |
| total_points | text/PK/FK | integer |
| valid_from | text/PK/FK | date |
| valid_to | text/PK/FK | date |
| run_id | text/PK/FK | bigint |

## history.dancer_roles_history
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| dancer_id | text/PK/FK | integer |
| dancer_name | text/PK/FK | text |
| dominate_role | text/PK/FK | text |
| dominate_required | text/PK/FK | text |
| dominate_allowed | text/PK/FK | text |
| non_dominate_role | text/PK/FK | text |
| non_dominate_required | text/PK/FK | text |
| non_dominate_allowed | text/PK/FK | text |
| non_dominate_recommended | text/PK/FK | text |
| non_dominate_role_highest_level_points | text/PK/FK | text |
| non_dominate_role_highest_level | text/PK/FK | text |
| valid_from | text/PK/FK | date |
| valid_to | text/PK/FK | date |
| run_id | text/PK/FK | bigint |

## history.events_list_changes
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| change_id | text/PK/FK | bigint |
| run_id | text/PK/FK | integer |
| change_type | text/PK/FK | text |
| source_fingerprint | text/PK/FK | text |
| event_name | text/PK/FK | text |
| start_date | text/PK/FK | date |
| end_date | text/PK/FK | date |
| location_raw | text/PK/FK | text |
| url | text/PK/FK | text |
| snapshot | text/PK/FK | jsonb |

## history.events_list_runs
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| run_id | text/PK/FK | integer |
| scraped_at | text/PK/FK | timestamp with time zone |
| source | text/PK/FK | text |
| total_events | text/PK/FK | integer |
| added_count | text/PK/FK | integer |
| removed_count | text/PK/FK | integer |
| unchanged_count | text/PK/FK | integer |

## history.parse_runs
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| run_id | text/PK/FK | bigint |
| started_at | text/PK/FK | timestamp with time zone |
| finished_at | text/PK/FK | timestamp with time zone |
| source | text/PK/FK | text |
| probe_hash | text/PK/FK | text |
| rows_results | text/PK/FK | integer |
| rows_points | text/PK/FK | integer |
| points_changed | text/PK/FK | integer |
| dancers_added | text/PK/FK | integer |
| status | text/PK/FK | text |

## staging.changed_dancer_role_info
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| dancer_id | text/PK/FK | text |
| dancer_name | text/PK/FK | text |
| dominate_role | text/PK/FK | text |
| dominate_required | text/PK/FK | text |
| dominate_allowed | text/PK/FK | text |
| non_dominate_role | text/PK/FK | text |
| non_dominate_required | text/PK/FK | text |
| non_dominate_allowed | text/PK/FK | text |
| non_dominate_recommended | text/PK/FK | text |
| non_dominate_role_highest_level_points | text/PK/FK | text |
| non_dominate_role_highest_level | text/PK/FK | text |
| update_date | text/PK/FK | text |

## staging.changed_dancers_points_info
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| dancer_id | text/PK/FK | text |
| role | text/PK/FK | text |
| dance | text/PK/FK | text |
| level | text/PK/FK | text |
| total_points | text/PK/FK | text |
| update_date | text/PK/FK | text |

## staging.dancer_role_info
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| dancer_id | text/PK/FK | text |
| dancer_name | text/PK/FK | text |
| dominate_role | text/PK/FK | text |
| dominate_required | text/PK/FK | text |
| dominate_allowed | text/PK/FK | text |
| non_dominate_role | text/PK/FK | text |
| non_dominate_required | text/PK/FK | text |
| non_dominate_allowed | text/PK/FK | text |
| non_dominate_recommended | text/PK/FK | text |
| non_dominate_role_highest_level_points | text/PK/FK | text |
| non_dominate_role_highest_level | text/PK/FK | text |
| update_date | text/PK/FK | text |

## staging.dancers_points_info
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| dancer_id | text/PK/FK | text |
| role | text/PK/FK | text |
| dance | text/PK/FK | text |
| level | text/PK/FK | text |
| total_points | text/PK/FK | text |
| update_date | text/PK/FK | text |

## staging.dancers_results_info
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| dancer_id | text/PK/FK | text |
| event_dance | text/PK/FK | text |
| event_competition | text/PK/FK | text |
| event_role | text/PK/FK | text |
| event_name_id | text/PK/FK | text |
| event_name | text/PK/FK | text |
| event_result | text/PK/FK | text |
| event_points | text/PK/FK | text |
| event_month | text/PK/FK | text |
| event_year | text/PK/FK | text |
| location_id | text/PK/FK | text |
| event_year_and_month | text/PK/FK | text |
| event_result_standardized | text/PK/FK | text |

## staging.events_wsdc
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| event_instance_id | text/PK/FK | text |
| id | text/PK/FK | text |
| name | text/PK/FK | text |
| location | text/PK/FK | text |
| url | text/PK/FK | text |
| date | text/PK/FK | text |
| parsed_date | text/PK/FK | text |
| event_year | text/PK/FK | text |
| event_month | text/PK/FK | text |
| event_year_month | text/PK/FK | text |

## staging.location_info
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| location_id | text/PK/FK | text |
| event_city | text/PK/FK | text |
| event_state | text/PK/FK | text |
| event_country | text/PK/FK | text |
| latitude | text/PK/FK | text |
| longitude | text/PK/FK | text |
| event_location | text/PK/FK | text |
| event_location_standardized | text/PK/FK | text |
| coordinates_valid | text/PK/FK | text |

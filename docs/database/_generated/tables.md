# Generated tables

[auto] Regenerate with `python scripts/generate_schema_docs.py`

## core.dancer_aliases
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| alias | text/PK/FK | — |
| dancer_id | text/PK/FK | — |
| source | text/PK/FK | — |
| notes | text/PK/FK | — |

## core.dancer_points
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| dancer_id | text/PK/FK | — |
| role | text/PK/FK | — |
| dance | text/PK/FK | — |
| level | text/PK/FK | — |
| total_points | text/PK/FK | — |
| update_date | text/PK/FK | — |

## core.dancer_roles
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| dancer_id | text/PK/FK | — |
| dominate_role | text/PK/FK | — |
| dominate_required | text/PK/FK | — |
| dominate_allowed | text/PK/FK | — |
| non_dominate_role | text/PK/FK | — |
| non_dominate_required | text/PK/FK | — |
| non_dominate_allowed | text/PK/FK | — |
| non_dominate_recommended | text/PK/FK | — |
| non_dominate_role_highest_level_points | text/PK/FK | — |
| non_dominate_role_highest_level | text/PK/FK | — |
| update_date | text/PK/FK | — |

## core.dancers
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| dancer_id | text/PK/FK | — |
| dancer_name | text/PK/FK | — |

## core.event_aliases
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| alias | text/PK/FK | — |
| event_id | text/PK/FK | — |

## core.event_catalog

One row per WSDC registry event (brand): URL, typical location, edition stats.

| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| event_id | text/PK/FK | — |
| canonical_name | text/PK/FK | — |
| url | text/PK/FK | — |
| registry_status | text/PK/FK | — |
| typical_city | text/PK/FK | — |
| typical_state | text/PK/FK | — |
| typical_country | text/PK/FK | — |
| typical_location | text/PK/FK | — |
| first_edition_year | text/PK/FK | — |
| last_edition_year | text/PK/FK | — |
| edition_count | text/PK/FK | — |
| total_result_rows | text/PK/FK | — |
| upcoming_start_date | text/PK/FK | — |
| upcoming_location | text/PK/FK | — |
| updated_at | text/PK/FK | — |

## core.event_editions

One row per event held in a given year/month; join results on (event_id, event_year, event_month).

| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| edition_id | text/PK/FK | — |
| event_id | text/PK/FK | — |
| event_year | text/PK/FK | — |
| event_month | text/PK/FK | — |
| edition_date | text/PK/FK | — |
| location_id | text/PK/FK | — |
| place_city | text/PK/FK | — |
| place_state | text/PK/FK | — |
| place_country | text/PK/FK | — |
| location_raw | text/PK/FK | — |
| result_rows | text/PK/FK | — |

## core.event_instances
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| event_instance_id | text/PK/FK | — |
| event_id | text/PK/FK | — |
| location_id | text/PK/FK | — |
| location_raw | text/PK/FK | — |
| date_raw | text/PK/FK | — |
| event_date | text/PK/FK | — |
| event_year | text/PK/FK | — |
| event_month | text/PK/FK | — |

## core.events
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| event_id | text/PK/FK | — |
| name | text/PK/FK | — |
| url | text/PK/FK | — |

## core.events_list_current

Latest schedule snapshot: one row per logical event (nearest upcoming edition).

| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| schedule_event_key | text/PK/FK | — |
| source_fingerprint | text/PK/FK | — |
| canonical_event_id | text/PK/FK | — |
| event_name | text/PK/FK | — |
| canonical_name | text/PK/FK | — |
| original_date | text/PK/FK | — |
| start_date | text/PK/FK | — |
| end_date | text/PK/FK | — |
| results_year | text/PK/FK | — |
| results_month | text/PK/FK | — |
| location_raw | text/PK/FK | — |
| country | text/PK/FK | — |
| country_flag | text/PK/FK | — |
| url | text/PK/FK | — |
| status_event | text/PK/FK | — |
| confirmed | text/PK/FK | — |
| canceled | text/PK/FK | — |
| on_hiatus | text/PK/FK | — |
| match_status | text/PK/FK | — |
| match_method | text/PK/FK | — |
| match_confidence | text/PK/FK | — |
| upcoming_editions | text/PK/FK | — |
| updated_at | text/PK/FK | — |
| last_run_id | text/PK/FK | — |

## core.levels
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| level | text/PK/FK | — |
| level_abbr | text/PK/FK | — |
| sort_order | text/PK/FK | — |

## core.locations
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| location_id | text/PK/FK | — |
| event_city | text/PK/FK | — |
| event_state | text/PK/FK | — |
| event_country | text/PK/FK | — |
| latitude | text/PK/FK | — |
| longitude | text/PK/FK | — |
| event_location | text/PK/FK | — |
| event_location_standardized | text/PK/FK | — |
| coordinates_valid | text/PK/FK | — |

## core.results
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| result_id | text/PK/FK | — |
| dancer_id | text/PK/FK | — |
| event_id | text/PK/FK | — |
| location_id | text/PK/FK | — |
| dance | text/PK/FK | — |
| division | text/PK/FK | — |
| role | text/PK/FK | — |
| event_year | text/PK/FK | — |
| event_month | text/PK/FK | — |
| event_date | text/PK/FK | — |
| result_raw | text/PK/FK | — |
| result_standardized | text/PK/FK | — |
| points | text/PK/FK | — |

## core.scheduled_events

Edition-level schedule archive keyed by source_fingerprint (all scrape observations).

| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| source_fingerprint | text/PK/FK | — |
| event_name | text/PK/FK | — |
| original_date | text/PK/FK | — |
| start_date | text/PK/FK | — |
| end_date | text/PK/FK | — |
| results_year | text/PK/FK | — |
| results_month | text/PK/FK | — |
| location_raw | text/PK/FK | — |
| country | text/PK/FK | — |
| country_flag | text/PK/FK | — |
| url | text/PK/FK | — |
| status_event | text/PK/FK | — |
| confirmed | text/PK/FK | — |
| canceled | text/PK/FK | — |
| on_hiatus | text/PK/FK | — |
| is_active | text/PK/FK | — |
| first_seen_at | text/PK/FK | — |
| last_seen_at | text/PK/FK | — |
| last_run_id | text/PK/FK | — |

## history.dancer_names_history
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| dancer_id | text/PK/FK | — |
| dancer_name | text/PK/FK | — |
| valid_from | text/PK/FK | — |
| valid_to | text/PK/FK | — |
| run_id | text/PK/FK | — |

## history.dancer_points_history
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| dancer_id | text/PK/FK | — |
| role | text/PK/FK | — |
| dance | text/PK/FK | — |
| level | text/PK/FK | — |
| total_points | text/PK/FK | — |
| valid_from | text/PK/FK | — |
| valid_to | text/PK/FK | — |
| run_id | text/PK/FK | — |

## history.dancer_roles_history
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| dancer_id | text/PK/FK | — |
| dancer_name | text/PK/FK | — |
| dominate_role | text/PK/FK | — |
| dominate_required | text/PK/FK | — |
| dominate_allowed | text/PK/FK | — |
| non_dominate_role | text/PK/FK | — |
| non_dominate_required | text/PK/FK | — |
| non_dominate_allowed | text/PK/FK | — |
| non_dominate_recommended | text/PK/FK | — |
| non_dominate_role_highest_level_points | text/PK/FK | — |
| non_dominate_role_highest_level | text/PK/FK | — |
| valid_from | text/PK/FK | — |
| valid_to | text/PK/FK | — |
| run_id | text/PK/FK | — |

## history.events_list_changes
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| change_id | text/PK/FK | — |
| run_id | text/PK/FK | — |
| change_type | text/PK/FK | — |
| source_fingerprint | text/PK/FK | — |
| event_name | text/PK/FK | — |
| start_date | text/PK/FK | — |
| end_date | text/PK/FK | — |
| location_raw | text/PK/FK | — |
| url | text/PK/FK | — |
| snapshot | text/PK/FK | — |

## history.events_list_runs
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| run_id | text/PK/FK | — |
| scraped_at | text/PK/FK | — |
| source | text/PK/FK | — |
| total_events | text/PK/FK | — |
| added_count | text/PK/FK | — |
| removed_count | text/PK/FK | — |
| unchanged_count | text/PK/FK | — |

## history.parse_runs
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| run_id | text/PK/FK | — |
| started_at | text/PK/FK | — |
| finished_at | text/PK/FK | — |
| source | text/PK/FK | — |
| probe_hash | text/PK/FK | — |
| rows_results | text/PK/FK | — |
| rows_points | text/PK/FK | — |
| points_changed | text/PK/FK | — |
| dancers_added | text/PK/FK | — |
| status | text/PK/FK | — |

## staging.changed_dancer_role_info
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| dancer_id | text/PK/FK | — |
| dancer_name | text/PK/FK | — |
| dominate_role | text/PK/FK | — |
| dominate_required | text/PK/FK | — |
| dominate_allowed | text/PK/FK | — |
| non_dominate_role | text/PK/FK | — |
| non_dominate_required | text/PK/FK | — |
| non_dominate_allowed | text/PK/FK | — |
| non_dominate_recommended | text/PK/FK | — |
| non_dominate_role_highest_level_points | text/PK/FK | — |
| non_dominate_role_highest_level | text/PK/FK | — |
| update_date | text/PK/FK | — |

## staging.changed_dancers_points_info
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| dancer_id | text/PK/FK | — |
| role | text/PK/FK | — |
| dance | text/PK/FK | — |
| level | text/PK/FK | — |
| total_points | text/PK/FK | — |
| update_date | text/PK/FK | — |

## staging.dancer_role_info
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| dancer_id | text/PK/FK | — |
| dancer_name | text/PK/FK | — |
| dominate_role | text/PK/FK | — |
| dominate_required | text/PK/FK | — |
| dominate_allowed | text/PK/FK | — |
| non_dominate_role | text/PK/FK | — |
| non_dominate_required | text/PK/FK | — |
| non_dominate_allowed | text/PK/FK | — |
| non_dominate_recommended | text/PK/FK | — |
| non_dominate_role_highest_level_points | text/PK/FK | — |
| non_dominate_role_highest_level | text/PK/FK | — |
| update_date | text/PK/FK | — |

## staging.dancers_points_info
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| dancer_id | text/PK/FK | — |
| role | text/PK/FK | — |
| dance | text/PK/FK | — |
| level | text/PK/FK | — |
| total_points | text/PK/FK | — |
| update_date | text/PK/FK | — |

## staging.dancers_results_info
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| dancer_id | text/PK/FK | — |
| event_dance | text/PK/FK | — |
| event_competition | text/PK/FK | — |
| event_role | text/PK/FK | — |
| event_name_id | text/PK/FK | — |
| event_name | text/PK/FK | — |
| event_result | text/PK/FK | — |
| event_points | text/PK/FK | — |
| event_month | text/PK/FK | — |
| event_year | text/PK/FK | — |
| location_id | text/PK/FK | — |
| event_year_and_month | text/PK/FK | — |
| event_result_standardized | text/PK/FK | — |

## staging.events_wsdc
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| event_instance_id | text/PK/FK | — |
| id | text/PK/FK | — |
| name | text/PK/FK | — |
| location | text/PK/FK | — |
| url | text/PK/FK | — |
| date | text/PK/FK | — |
| parsed_date | text/PK/FK | — |
| event_year | text/PK/FK | — |
| event_month | text/PK/FK | — |
| event_year_month | text/PK/FK | — |

## staging.location_info
| Column | Migration parse | Live type |
|--------|-----------------|-----------|
| location_id | text/PK/FK | — |
| event_city | text/PK/FK | — |
| event_state | text/PK/FK | — |
| event_country | text/PK/FK | — |
| latitude | text/PK/FK | — |
| longitude | text/PK/FK | — |
| event_location | text/PK/FK | — |
| event_location_standardized | text/PK/FK | — |
| coordinates_valid | text/PK/FK | — |

# Export views

Read-only `export.*` views define the Tableau CSV contract. `export.py` copies each view to `data/*.csv`.

## Default export map

From `export.py`:

| View | CSV file | In default export |
|------|----------|-------------------|
| `export.dancers_points_info` | `dancers_points_info.csv` | Yes |
| `export.dancer_role_info` | `dancer_role_info.csv` | Yes |
| `export.dancers_results_info` | `dancers_results_info.csv` | Yes |
| `export.location_info` | `location_info.csv` | Yes |
| `export.events_wsdc` | `events_wsdc.csv` | Yes |
| `export.event_catalog` | `event_catalog.csv` | Yes |
| `export.event_editions` | `event_editions.csv` | Yes |
| `export.scheduled_events` | `scheduled_events.csv` | Yes |
| `export.changed_dancer_points_info` | `changed_dancer_points_info.csv` | Yes |
| `export.changed_dancer_role_info` | `changed_dancer_role_info.csv` | Yes |
| `export.changed_dancer_name_info` | `changed_dancer_name_info.csv` | Yes |
| `export.results_by_event` | `results_by_event.csv` | No (`--include-results-by-event`) |
| `export.dancers_results_with_name` | `dancers_results_with_name.csv` | No (`--include-results-with-name`) |
| `derived.*` (post-export) | `divisional_structure.csv`, `divisional_structure_only_dominate_role.csv`, `dancer_transitions.csv` | Yes (after DB export) |
| `export.geo_events` | — | Not wired in export.py |
| `export.results_by_geo_event` | — | Not wired in export.py |
| `export.scheduled_event_editions` | — | Not in default export |
| `export.scheduled_events_legacy` | — | Deprecated; query manually if needed |

## export.dancers_points_info

**Source:** `core.dancer_points`

| Column | Type | Description |
|--------|------|-------------|
| dancer_id | int | Dancer id |
| role | text | Leader / Follower |
| dance | text | Dance |
| level | text | Level |
| total_points | int | Points |
| update_date | date | API update date |

## export.dancer_role_info

**Source:** `core.dancer_roles` JOIN `core.dancers`

| Column | Type | Description |
|--------|------|-------------|
| dancer_id | int | Dancer id |
| dancer_name | text | Name |
| dominate_role | text | Primary role |
| dominate_required | text | Required level |
| dominate_allowed | text | Allowed |
| non_dominate_role | text | Secondary role |
| non_dominate_required | text | Required |
| non_dominate_allowed | text | Allowed |
| non_dominate_recommended | text | Recommended |
| non_dominate_role_highest_level_points | text | Points |
| non_dominate_role_highest_level | text | Level |
| update_date | date | Snapshot date |

## export.dancers_results_info

**Source:** `core.results` LEFT JOIN `core.events`

Legacy column names preserved for old workbooks.

| Column | Type | Description |
|--------|------|-------------|
| dancer_id | int | Dancer |
| event_dance | text | `results.dance` |
| event_competition | text | `results.division` |
| event_role | text | Lowercase role |
| event_result | text | `result_raw` |
| event_points | int | Points |
| event_name | text | `events.name` or `event_name_raw` |
| location_id | int | Location FK |
| event_year | int | Year |
| event_month | int | Month |
| event_year_and_month | date | Edition date |
| event_result_standardized | text | `result_standardized` (migration 020) |

Note: no `event_id` in export — join via `event_name` + year/month or use `results_by_event.csv`.

## export.location_info

**Source:** `core.locations`

| Column | Type | Description |
|--------|------|-------------|
| location_id | int | Id |
| event_city | text | City |
| event_state | text | State |
| event_country | text | Country |
| latitude | numeric | Lat |
| longitude | numeric | Lon |
| event_location | text | Label |
| event_location_standardized | text | Normalized label |
| coordinates_valid | boolean | Coords verified |

## export.events_wsdc

**Source:** `core.event_instances` JOIN `core.events`

| Column | Type | Description |
|--------|------|-------------|
| id | int | `event_id` |
| name | text | Registry name |
| location | text | Raw location |
| url | text | URL |
| date | text | Raw date label |
| parsed_date | date | Parsed edition date |
| event_year | int | Year |
| event_month | int | Month |
| event_year_month | text | `YYYY-MM` when derivable |

## export.event_catalog

**Source:** `core.event_catalog` — see [core.md](core.md).

## export.event_editions

**Source:** `core.event_editions` JOIN `core.event_catalog`

Adds `event_name`, `url`, `typical_location`, `registry_status` from catalog.

## export.scheduled_events

**Source:** `core.events_list_current` — one row per logical upcoming event.

See [../tableau/dashboards-migration.md](../tableau/dashboards-migration.md).

## export.scheduled_event_editions

**Source:** `core.scheduled_events` WHERE `is_active`

All active edition rows on WSDC site (multi-year listings).

## export.scheduled_events_legacy

**Source:** `core.scheduled_events` WHERE `is_active` — deprecated edition-level shape.

## export.changed_dancer_points_info

**Source:** `history.dancer_points_history`

`update_date` = `valid_from`. See [../architecture/scd2-history.md](../architecture/scd2-history.md).

## export.changed_dancer_role_info

**Source:** `history.dancer_roles_history` (division changes only; `dancer_name` is display-only)

Column order matches legacy `changed_dancer_role_info.csv`.

## export.changed_dancer_name_info

**Source:** `history.dancer_names_history`

Columns: `dancer_id`, `dancer_name`, `update_date` (`valid_from`).

## export.dancers_results_with_name

**Source:** `core.results` + `core.dancer_name_at(dancer_id, as_of_date)`

Optional; enable with `python export.py --include-results-with-name`.

`as_of_date` = `event_date`, or `make_date(event_year, event_month, 1)` when `event_date` is null. When both are null, `dancer_name_at` returns the current name from `core.dancers`.

## export.results_by_event

**Source:** Denormalized join of results + catalog + editions (~47 MB).

Optional; enable with `python export.py --include-results-by-event`.

## Derived analytics CSVs (post-export)

Not Supabase views. Built by `transform/divisional_exports.py` after view export from `changed_dancer_role_info.csv` (fallback: `dancer_role_info.csv`).

| CSV | Builder | Merge policy |
|-----|---------|--------------|
| `divisional_structure.csv` | melt + aggregate all roles | append dates newer than baseline max |
| `divisional_structure_only_dominate_role.csv` | dominate role only | same |
| `dancer_transitions.csv` | current vs previous **full** parse snapshot | append new `Update Date` only |

Skip with `python export.py --skip-derived-exports`. Column contract: [../tableau/csv-contract.md](../tableau/csv-contract.md).

## export.geo_events (migration 019)

**Source:** `core.event_catalog` with computed `geo_key`, `geo_event_key`, `metro_label`.

Not exported to CSV by default. Query in Supabase or add to `export.py` when Tableau workbooks need geo dimension file.

## export.results_by_geo_event (migration 019)

**Source:** `core.results` + `export.geo_events` + `core.event_editions`

Includes `event_name_raw`. Optional large export.

## Drift risks

| Risk | Mitigation |
|------|------------|
| View changed, CSV stale | Re-run `export.py` after migrations |
| Column rename breaks Tableau | Preserve legacy view column aliases in migrations |
| `event_editions` empty | Preprocess dates before load |

## Related

- [../tableau/csv-contract.md](../tableau/csv-contract.md) — analyst-facing column reference
- [migrations.md](migrations.md) — which migration defines each view

# CSV export contract

Column reference for committed `data/*.csv` files. Source views in [../database/export-views.md](../database/export-views.md).

## dancers_points_info.csv

**Grain:** one row per `(dancer_id, role, dance, level)`  
**View:** `export.dancers_points_info`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| dancer_id | integer | NO | WSDC dancer id |
| role | string | NO | Leader / Follower |
| dance | string | NO | Dance code |
| level | string | NO | Full level name |
| total_points | integer | NO | Current points |
| update_date | date | YES | API update date |

## dancer_role_info.csv

**Grain:** one row per dancer  
**View:** `export.dancer_role_info`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| dancer_id | integer | NO | Dancer id |
| dancer_name | string | YES | Name |
| dominate_role | string | YES | Primary role |
| dominate_required | string | YES | Required level |
| dominate_allowed | string | YES | Allowed levels |
| non_dominate_role | string | YES | Secondary role |
| non_dominate_required | string | YES | Required level |
| non_dominate_allowed | string | YES | Allowed levels |
| non_dominate_recommended | string | YES | Recommended |
| non_dominate_role_highest_level_points | string | YES | Points |
| non_dominate_role_highest_level | string | YES | Level |
| update_date | date | YES | Snapshot date |

## dancers_results_info.csv

**Grain:** one competition result  
**View:** `export.dancers_results_info`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| dancer_id | integer | NO | Dancer |
| event_dance | string | YES | Dance |
| event_competition | string | YES | Division / level |
| event_role | string | YES | leader / follower (lowercase) |
| event_result | string | YES | Placement raw |
| event_points | integer | YES | Points |
| event_name | string | YES | Catalog or raw title |
| location_id | integer | YES | Location FK |
| event_year | integer | YES | Edition year |
| event_month | integer | YES | Edition month |
| event_year_and_month | date | YES | Edition date |
| event_result_standardized | string | YES | Normalized placement (migration 020) |

Note: legacy export has no `event_id` column — join via `event_name` + year/month or use optional `results_by_event.csv`.

## location_info.csv

**Grain:** one location  
**View:** `export.location_info`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| location_id | integer | NO | Location id |
| event_city | string | YES | City |
| event_state | string | YES | State / region |
| event_country | string | YES | Country |
| latitude | decimal | YES | Latitude |
| longitude | decimal | YES | Longitude |
| event_location | string | YES | Display label |
| event_location_standardized | string | YES | Normalized label (migration 020) |
| coordinates_valid | boolean | YES | Coords verified (migration 020) |

## events_wsdc.csv

**Grain:** one registry instance row  
**View:** `export.events_wsdc`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | integer | NO | WSDC event_id |
| name | string | NO | Registry name |
| location | string | YES | Raw location |
| url | string | YES | URL |
| date | string | YES | Raw date label |
| parsed_date | date | YES | Parsed edition date (migration 020) |
| event_year | integer | YES | Year (migration 020) |
| event_month | integer | YES | Month (migration 020) |
| event_year_month | string | YES | `YYYY-MM` when year/month known (migration 020) |

## event_catalog.csv

**Grain:** one event brand  
**View:** `export.event_catalog`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| event_id | integer | NO | Registry id |
| canonical_name | string | NO | Dashboard name |
| url | string | YES | Event URL |
| registry_status | string | YES | active / inactive / merged |
| typical_city | string | YES | Mode city |
| typical_state | string | YES | Mode state |
| typical_country | string | YES | Mode country |
| typical_location | string | YES | Combined label |
| first_edition_year | integer | YES | First year |
| last_edition_year | integer | YES | Last year |
| edition_count | integer | NO | Edition count |
| total_result_rows | integer | NO | Result rows |
| unique_dancers | integer | NO | Distinct dancers |
| upcoming_start_date | date | YES | Next scheduled |
| upcoming_location | string | YES | Next location |
| updated_at | datetime | NO | Catalog rebuild time |

## event_editions.csv

**Grain:** one event × year × month  
**View:** `export.event_editions`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| edition_id | integer | NO | Edition surrogate |
| event_id | integer | NO | Registry id |
| event_name | string | NO | From catalog |
| event_year | integer | NO | Year |
| event_month | integer | NO | Month |
| edition_date | date | YES | Month sentinel from results (`YYYY-MM-01`) |
| start_date | date | YES | Inclusive first day (calendar/list) |
| end_date | date | YES | Inclusive last day |
| date_source | string | YES | `wsdc_calendar` / `wsdc_events_list` |
| calendar_status | string | YES | `scheduled` / `unconfirmed` / `hiatus` / `cancelled` |
| event_occurred | boolean | YES | FALSE if hiatus/cancelled |
| location_id | integer | YES | Location FK |
| place_city | string | YES | City |
| place_state | string | YES | State |
| place_country | string | YES | Country |
| location_raw | string | YES | Raw string |
| result_rows | integer | NO | Results count |
| unique_dancers | integer | NO | Dancers count |
| url | string | YES | Event URL |
| typical_location | string | YES | Brand typical location |
| registry_status | string | YES | Status |

## edition_calendar_dates.csv

**Grain:** planned edition dates (durable; survives rebuild)  
**View:** `export.edition_calendar_dates`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| event_id | integer | NO | Registry id |
| event_name | string | YES | Catalog name |
| event_year | integer | NO | Year |
| event_month | integer | NO | Month |
| planned_start_date | date | YES | Inclusive start |
| planned_end_date | date | YES | Inclusive end |
| calendar_status | string | NO | Status flag |
| date_source | string | NO | Source |
| source_fingerprint | string | YES | Fingerprint |
| calendar_title | string | YES | Calendar title |
| url | string | YES | URL |
| match_via | string | YES | Match method |
| scraped_at | timestamp | YES | Scrape time |
| updated_at | timestamp | NO | Upsert time |

## scheduled_events.csv

**Grain:** one upcoming event brand (nearest edition)  
**View:** `export.scheduled_events`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| schedule_event_key | string | NO | Stable schedule key |
| source_fingerprint | string | NO | Current edition hash |
| canonical_event_id | integer | YES | Matched registry id |
| event_name | string | NO | Name on WSDC site |
| canonical_name | string | YES | Matched catalog name |
| original_date | string | YES | Date string |
| start_date | date | YES | Start |
| end_date | date | YES | End |
| results_year | integer | YES | Results year |
| results_month | integer | YES | Results month |
| location_raw | string | YES | Location |
| country | string | YES | Country |
| country_flag | string | YES | Flag |
| url | string | YES | URL |
| status_event | string | YES | Registry / trial |
| registry_trial_status | string | YES | Same as status_event |
| confirmed | boolean | YES | Confirmed |
| canceled | boolean | YES | Canceled |
| on_hiatus | boolean | YES | Hiatus |
| match_status | string | YES | Mapping status |
| match_method | string | YES | Match method |
| match_confidence | float | YES | Score |
| upcoming_editions | integer | NO | Future edition count |
| updated_at | datetime | NO | Last sync |

## changed_dancer_points_info.csv

**Grain:** one points change version  
**View:** `export.changed_dancer_points_info`

Same columns as `dancers_points_info.csv`. `update_date` = change effective date (`valid_from`), not necessarily current API date.

## changed_dancer_role_info.csv

**Grain:** one role-summary change version  
**View:** `export.changed_dancer_role_info`

Same 12 columns as `dancer_role_info.csv` (column order matches legacy). `update_date` = `valid_from`. Division changes only; `dancer_name` is display-only on each version row.

## changed_dancer_name_info.csv

**Grain:** one display-name change version  
**View:** `export.changed_dancer_name_info`

| Column | Type | Description |
|--------|------|-------------|
| dancer_id | integer | WSDC id |
| dancer_name | string | Name during `[valid_from, valid_to]` |
| update_date | date | `valid_from` |

## Optional: dancers_results_with_name.csv

**Flag:** `python export.py --include-results-with-name`  
**View:** `export.dancers_results_with_name`

Same as `dancers_results_info.csv` plus `dancer_name` from `core.dancer_name_at(dancer_id, as_of)`.

`as_of` = `event_date`, or first day of `event_year`/`event_month` when date is missing; current name when both are null.

## Optional: results_by_event.csv

**Flag:** `python export.py --include-results-by-event`  
**View:** `export.results_by_event`

Denormalized results with catalog + edition fields. ~47 MB. See [../database/export-views.md](../database/export-views.md).

## tier_rules.csv

**Grain:** one row per `(rules_version, tier)`  
**View:** `export.tier_rules`  
**Source:** [`transform/knowledge/tier_rules.py`](../../transform/knowledge/tier_rules.py) via `scripts/load_tier_rules.py`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| rules_version | string | NO | Rules edition id (e.g. `2018`, `2026`) |
| valid_from / valid_to | date | YES | Validity window (`valid_to` null = current) |
| tier_basis | string | NO | `none` / `smaller_role` / `per_role` |
| min_role_competitors | integer | NO | Minimum for points eligibility |
| tier | integer | NO | `0` = flat pre-tier scale; else 1–6 |
| min_competitors / max_competitors | integer | YES | Competitor range for this Tier (`max` null = open) |
| prelim_rounds | integer | NO | Typical / mandatory rounds |
| finalist_points | integer | NO | Points for additional finalists |
| points_1st … points_5th | integer | YES | Chart 5 placement points |

See [../rules/tier-chart.md](../rules/tier-chart.md).

## edition_division_tiers.csv

**Grain:** one row per `(event_id, event_year, event_month, division, role, dance)`  
**View:** `export.edition_division_tiers`  
**Built by:** `db/build_edition_tiers.py` (after each points load)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| edition_id | integer | YES | FK-like to `event_editions` (rebuilt) |
| event_id / event_name | — | — | Event |
| event_year / event_month | integer | NO | Edition |
| division / role / dance | string | NO | Contest grain |
| rules_version | string | YES | Matched rules edition |
| observed_points_1..5 | integer | YES | Max points at each placement |
| finalists / scored_dancers | integer | NO | Observed counts |
| tier | integer | YES | Inferred Tier (`0` = flat pre-2007) |
| status | string | NO | `matched` / `legacy_chart` / `no_tier_system` / `no_points` / `ambiguous` / `unmatched` |
| vector_distance | integer | NO | L1 distance to chart (0 = exact) |
| rule_min/max_competitors | integer | YES | Chart range |
| est_min/max_competitors | integer | YES | Tightened by `scored_dancers` |
| range_conflict | boolean | NO | True if scored > rule_max |

## edition_division_entries.csv

**Grain:** one row per `(event_id, event_year, event_month, division, dance)`  
**View:** `export.edition_division_entries`

Rollup of both roles: `est_min_entries` / `est_max_entries` = sum of role estimates when both roles are present; otherwise null + `both_roles_present=false`.

## Derived analytics CSVs (post-export)

Built from `changed_dancer_role_info.csv` (fallback: `dancer_role_info.csv`) after Supabase views export. Same logic as legacy notebook aggregation cells.

| File | Grain | Key columns |
|------|-------|-------------|
| `divisional_structure.csv` | snapshot × division × role × type | `update_date`, `division`, `role`, **`type_options`**, `count_dancer` |
| `divisional_structure_only_dominate_role.csv` | same, dominate role only | `update_date`, `division`, `role`, **`type`**, `count_dancer` |
| `dancer_transitions.csv` | one division **A→B** change (both sides set; first seen) | `Update Date`, `Previous Division`, `Currently Division`, `Transition Type`, `Dancer Role`, `Dancer ID`, `Dancer Name` |

Committed baselines in `data/` are kept as-is. Export only appends **newer** snapshot dates (divisional). Transitions emit only real A→B (no clearance / first-appear), append new dates, and drop rows whose identity (`Dancer ID` + role + type + previous/current division) already exists — re-stamped full role exports must not replay the same deltas.

Skip with `python export.py --skip-derived-exports`.

## Row counts (order of magnitude, mid-2026)

| File | ~rows |
|------|-------|
| changed_dancer_role_info | 127,000 | Division versions (legacy split) |
| changed_dancer_name_info | 27,600 | Name versions (legacy split) |
| dancer_role_info | 27,200 |
| dancers_points_info | 50,600 |
| dancers_results_info | 194,000 |
| event_editions | 2,620 |
| event_catalog | 495 |
| events_wsdc | 2,620 |

## Related

- [joins.md](joins.md)
- [index.md](index.md)

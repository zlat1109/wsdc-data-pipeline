# Scheduled events dashboard migration

June 2026: `export.scheduled_events` switched from edition-level archive to brand-level current snapshot.

## What changed

| Before | After |
|--------|-------|
| Source: `core.scheduled_events` (all active editions) | Source: `core.events_list_current` |
| ~176 edition rows | ~165 brand rows |
| Columns: `is_active`, `first_seen_at`, `last_seen_at` | Columns: `schedule_event_key`, `canonical_event_id`, `match_*`, `upcoming_editions` |

## Which view / CSV to use

| Need | Source |
|------|--------|
| One row per event (nearest upcoming date) | `scheduled_events.csv` (default export) |
| Every future date on WSDC site | Query `export.scheduled_event_editions` (not default CSV) |
| Old workbook unchanged | `export.scheduled_events_legacy` (deprecated) |

## New columns

| Column | Meaning |
|--------|---------|
| `schedule_event_key` | Stable key for schedule brand |
| `canonical_event_id` | Link to points registry |
| `canonical_name` | Matched catalog title |
| `match_status` | Mapping outcome |
| `match_method` | How match was determined |
| `match_confidence` | Fuzzy score if applicable |
| `upcoming_editions` | Count of future editions on site |

## Migration steps

1. Replace data source with new `scheduled_events.csv` from repo
2. Update join: `canonical_event_id` → `event_catalog.event_id`
3. Remove dependencies on `is_active`, `first_seen_at`, `last_seen_at`
4. If dashboard counted editions, switch to `scheduled_event_editions` or adjust calc

## Files in repo

`data/events_list/` holds scrape artifacts (JSON/CSV/changelog). See [../transform/events-list.md](../transform/events-list.md).

## Related

- [joins.md](joins.md)
- [csv-contract.md](csv-contract.md) — `scheduled_events` columns

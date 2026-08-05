# Trial / list event geo

## Problem

Brand-new **Trial Event** rows from the WSDC events list often have city/country
text but no `location_id` / lat-lon until points results exist — and points may
reuse a wrong shared `location_id`.

## Source of truth (priority)

1. `event_website` — venue/hotel on the event site *(future phase)*
2. `events_list` — city/country from the WSDC list *(MVP)*
3. `points` — WSDC results location_id

## What this pipeline does (MVP)

| Step | Behavior |
|---|---|
| List sync (`scripts/sync_events_list.py`) | For **Trial Event** rows without `location_id`: `ensure_location` → reuse `location_info` / city-canonical coords / Google Maps; write `scheduled_events.location_id` + `location_source`. Does **not** rewrite Registry coverage. |
| Weekly preprocess | `seed_result_locations_from_schedule`: fill empty lids; for Trial names, replace wrong lid unless `EVENT_NAME_LOCATION_OVERRIDES` applies. |
| Quality | Finding `TRIAL_SCHEDULE_GEO_GAP`; Telegram events-list message shows `geo_review`. |

## Schema

Migration `030_scheduled_events_location.sql`:

- `core.scheduled_events.location_id` / `location_source`
- `core.events_list_current.location_id` / `location_source`
- Export views include both columns

`location_source` vocabulary: `location_info` | `city_canonical` | `google_maps` | `event_website` | `unresolved`

## Secrets

Wire `GOOGLE_MAPS_API_KEY` in:

- `.github/workflows/sync-events-list.yml`
- `.github/workflows/full-parse.yml` (preprocess seed path)

If the secret is missing, reuse/canonical still run; unresolved trials go to review.

## Safety (post-#96 review)

- New `location_id` values use `max(CSV max, DB max) + 1` (`id_floor` from `core.locations`).
- Upsert looks up `lower(btrim(event_location))` before insert; unique conflicts remap to the owner id.
- `location_info.csv` is written **after** a successful DB commit (offline `--skip-db` may write immediately).

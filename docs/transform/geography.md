# Geography normalization

Locations are normalized for consistent maps, joins, and geo-aware event deduplication.

## Module layout

| File | Role |
|------|------|
| `transform/geography/canonical.py` | City keys, coordinate lookup |
| `transform/geography/normalize.py` | String cleanup |
| `transform/geography/resolve.py` | Parse `"City, ST USA"` patterns |
| `transform/geography/corrections.py` | Row-level fixes |
| `transform/geography/constants.py` | Country/state constants |
| `transform/geography/geo_event.py` | `geo_key`, metro clusters, split classification |
| `transform/knowledge/locations.py` | `LOCATION_ID_CORRECTIONS` by id |

## geo_key

`geo_event.geo_key(city, state, country)` → stable lowercase fingerprint:

```text
denver|colorado|united_states
singapore|singapore
metro:greater_boston_ma
```

Used for merge gate in `scripts/merge_event_ids.py` and quality audit split checks.

## Metro clusters

`METRO_CLUSTERS` in `geo_event.py`:

| Cluster id | Cities | Display label |
|------------|--------|---------------|
| `greater_boston_ma` | Boston, Framingham (MA, US) | Boston / Framingham, MA |

Both cities count as one geo for duplicate `event_id` merge (Countdown Swing Boston).

## Location ID corrections

`LOCATION_ID_CORRECTIONS` patches known bad registry rows, e.g.:

- Singapore ids where city = country name
- Stockholm invalid coordinates

Applied in preprocess and `db/enrich_known_events.py` during load.

## Preprocess flow

1. Resolve location strings via `resolve.py`
2. Apply id-based corrections from knowledge
3. Standardize labels for `location_info.csv`
4. **Dedupe** duplicate result rows and collapse duplicate location ids (same city, multiple `location_id`)
5. Quality audit flags unmapped cities

Preprocess dedupe runs on every load (PR #14+). For data **already in Supabase** loaded before that fix, use `scripts/dedupe_core_data.py` — see [../operations/repair-scripts.md](../operations/repair-scripts.md#dedupe_core_datapy).

## Export

`export.location_info` mirrors `core.locations` (7 columns).

`export.geo_events` adds `geo_key` / `geo_event_key` at event brand level (migration 019).

## Repair scripts

```bash
python scripts/repair_locations.py
python scripts/dedupe_core_data.py --dry-run   # duplicate results / bloated locations only
python scripts/dedupe_core_data.py --apply
```

`repair_locations.py` runs enrich + catalog rebuild for corrected ids. `dedupe_core_data.py` is a targeted in-place dedupe; do not use it for NULL `location_id` or event-id merges.

## Related

- [../policies/event-geo-dedup.md](../policies/event-geo-dedup.md)
- [../architecture/identity-model.md](../architecture/identity-model.md)

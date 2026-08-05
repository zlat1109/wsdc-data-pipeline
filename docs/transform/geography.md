# Geography normalization

Locations are normalized for consistent maps, joins, and geo-aware event deduplication.

## Module layout

| File | Role |
|------|------|
| `transform/geography/canonical.py` | City keys, coordinate lookup |
| `transform/geography/normalize.py` | String cleanup |
| `transform/geography/resolve.py` | Fill `results.location_id` from `event_location` + location registry |
| `transform/geography/utils.py` | Shared `norm_value()` for empty/NaN → stripped string |
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

## Event-name location overrides (wrong shared location_id)

Some WSDC result rows reuse another event's `location_id` (classic case: Sweden
Westie Gala / Swedish Swing Summer Camp tagged as Wailea / Aloha Open `124`).

`EVENT_NAME_LOCATION_OVERRIDES` in `transform/knowledge/events.py` sets the
correct place string. Preprocess then **forces** `location_id` remap via
`force_result_locations_from_event_name_overrides` (because
`resolve_result_location_ids` only fills *empty* ids).

If the override target city is missing from `location_info`, the force step
**skips with a WARNING** (does not invent a new id). Add the place to the
registry or fix the override string.

### Resolve / lookup hardening

`build_location_lookup` sorts by numeric `location_id` so the lowest
(canonical) id wins when several registry rows share a key. Lookup also
registers the canonicalised form of each raw/standardised string so
two-part labels (`"Washington, DC"`) match three-part variants
(`"Washington, DC, United States"`).

`resolve_result_location_ids` still refuses to invent rows when
`location_info` is empty but results already carry ids. It also WARNINGs when
`max(results.location_id)` is far above `max(location_info.location_id)`
(incomplete registry / FK collision risk).

### Audit similar collisions

```bash
python scripts/audit_event_location_mismatches.py
```

Sections:
- **A** name/country hint vs results country
- **B** scheduled calendar country vs results mode country
- **C** catalog `typical_location` vs `upcoming_location` country mismatch
  (Freedom Swing pattern: typical stuck on wrong city while upcoming is correct;
  or a real series move — do **not** auto-remap moves without year-aware research)

Apply overrides to local export CSVs without full re-parse:

```bash
python scripts/apply_event_name_location_overrides_csv.py --dry-run
python scripts/apply_event_name_location_overrides_csv.py --apply
```

Preprocess quality audit emits:

| Code | Meaning |
|------|---------|
| `EVENT_NAME_LOCATION_COUNTRY_CONFLICT` | Event-name country hint ≠ `location_id` country |
| `EVENT_NAME_LOCATION_ID_COLLISION` | Same `event_name` spans **multiple** `location_id` values |
| `SCHEDULED_VS_RESULTS_COUNTRY_CONFLICT` | Calendar country ≠ results location country |
| `EVENT_ID_CANONICAL_LOCATION_MISMATCH` | Results/editions ≠ curated `event_id` canon (KNOWN / override / upcoming) |
| `CATALOG_TYPICAL_UPCOMING_CONFLICT` | Catalog typical ≠ upcoming country |

`EVENT_NAME_LOCATION_ID_COLLISION` is the Slovenian Open / Best of the Best /
NZ Open pattern. Not every hit is a bug: metro moves (Countdown Framingham→Boston)
and true series relocates (Sunny Side Crimea→Spain) also appear — triage by year.

**`EVENT_ID_CANONICAL_LOCATION_MISMATCH`** compares results/editions mode country
to a curated canon keyed by **`event_id`** (not event name):

1. `KNOWN_EVENT_METADATA[event_id].typical_location`
2. else `EVENT_NAME_LOCATION_OVERRIDES` via catalog name→id
3. else catalog `upcoming_location` (schedule-backed)

Does **not** treat results-derived `typical_location` alone as truth (circular).
Series moves listed in `KNOWN_SERIES_MOVES` are ignored.

**Supabase:** next full-parse preprocess rewrites `core.results.location_id` via
the same force step. Until then, local `data/*.csv` can diverge from DB export.
After adding overrides, also run the CSV apply script and remap live
`core.event_editions` / `core.event_catalog` typical_* (or wait for rebuild).

Known false friends (section C) that are often **series moves**, not stuck ids:
- Westie's Angels: historical Washington DC results; 2026 schedule Lyon
- Swingside Invitational: historical San Antonio; 2026 schedule Liège

Do not force-remap those without year-aware edition logic.

**Related Perth-area brands (two WSDC ids):** `Go West Swing Fest` (306,
Fremantle, 2019) and `Go West SwingFest` (367, Perth, 2024+) are separate
registry events. Alias maps Fest→SwingFest; year overrides restore Fremantle
for 2019 so `split_names_same_geo` stays clean. Pair is also in
`KEEP_SEPARATE_EVENT_PAIRS`. Do not merge ids without an explicit decision.

## Country aliases

`COUNTRY_STANDARDIZATION` maps `South Korea` / `Korea, South` / `Korea` →
`Republic of Korea`. Jeju duplicate id `395` merges to canonical `213`.

## Preprocess flow

1. Resolve location strings via `resolve.py` (`LOCATION_STRING_ALIASES` + lookup table)
2. Force remap from `EVENT_NAME_LOCATION_OVERRIDES` then
   `EVENT_NAME_YEAR_LOCATION_OVERRIDES` (`force_result_locations_from_event_name_overrides`)
   — year ranges keep relocating series on distinct cities (Sunny Side, Go West).
3. Standardize labels for `location_info.csv`; **clear `event_state` for non-US rows**
4. **Dedupe** duplicate result rows and collapse duplicate location ids (`LOCATION_ID_MERGE_MAP`)
5. Quality audit flags collisions (`EVENT_NAME_LOCATION_ID_COLLISION`), country mismatches, unmapped cities

Preprocess dedupe runs on every load (PR #14+). For data **already in Supabase** loaded before that fix, use `scripts/dedupe_core_data.py` — see [../operations/repair-scripts.md](../operations/repair-scripts.md#dedupe_core_datapy).

## Location ID merge map

`LOCATION_ID_MERGE_MAP` remaps duplicate registry ids to canonical rows during preprocess (`consolidate_location_ids`) and via `scripts/merge_location_ids.py` on Supabase. Add new pairs when reconciliation finds duplicate cities with different ids.

## Repair scripts

```bash
python scripts/repair_locations.py
python scripts/merge_location_ids.py --dry-run
python scripts/merge_location_ids.py --apply
python scripts/dedupe_core_data.py --dry-run   # duplicate results / bloated locations only
python scripts/dedupe_core_data.py --apply
```

`repair_locations.py` runs enrich + catalog rebuild for corrected ids. `merge_location_ids.py` applies merge map + field corrections + clears non-US `event_state`. `dedupe_core_data.py` is a targeted in-place dedupe; do not use it for NULL `location_id` or event-id merges.

`scripts/run_pipeline.py` runs `merge_location_ids.py --apply` and `dedupe_core_data.py --apply` after `repair_locations.py` as a post-load safety net.

## Export

`export.location_info` mirrors `core.locations` (7 columns).

`export.geo_events` adds `geo_key` / `geo_event_key` at event brand level (migration 019).

## Related

- [../policies/event-geo-dedup.md](../policies/event-geo-dedup.md)
- [../architecture/identity-model.md](../architecture/identity-model.md)

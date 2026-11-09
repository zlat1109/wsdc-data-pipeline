# Event locations — collaborator guide

Short path for using **cleaned WSDC event locations** (the geo layer behind Event Growth / Trends Monitor).  
This is a data hand-off, not a full pipeline tour.

## Start here

| Door | URL |
|------|-----|
| **Pipeline docs home** | [zlat1109.github.io/wsdc-data-pipeline](https://zlat1109.github.io/wsdc-data-pipeline/) |
| **This guide (docs site)** | [committee/event-locations-guide](https://zlat1109.github.io/wsdc-data-pipeline/committee/event-locations-guide/) |
| **This guide (GitHub)** | [`docs/committee/event-locations-guide.md`](https://github.com/zlat1109/wsdc-data-pipeline/blob/main/docs/committee/event-locations-guide.md) |
| **Live Event Growth (EN)** | [event_growth_dashboard_en.html](https://wsdc-analytics.github.io/event_growth_dashboard_en.html) |
| **Analytics site** | [wsdc-analytics.github.io](https://wsdc-analytics.github.io/) |

### Source repositories

| Repo | Role |
|------|------|
| [zlat1109/wsdc-data-pipeline](https://github.com/zlat1109/wsdc-data-pipeline) | Parse → Supabase → committed CSV extracts (`data/`) |
| [wsdc-analytics/wsdc-analytics.github.io](https://github.com/wsdc-analytics/wsdc-analytics.github.io) | Public site + dashboard payloads (`static/data/`) |

The pipeline **feeds** the analytics site on each successful export. The two repos stay separate on purpose.

Optional schema overview (warehouse shapes, not credentials): [Database docs](../database/index.md).

## What to open for locations

**Source of truth (pipeline CSVs on `main`):**

| File | Use |
|------|-----|
| [`data/location_info.csv`](https://github.com/zlat1109/wsdc-data-pipeline/blob/main/data/location_info.csv) | Canonical places: city / state / country + lat/lon |
| [`data/event_editions.csv`](https://github.com/zlat1109/wsdc-data-pipeline/blob/main/data/event_editions.csv) | Each edition → `location_id` + place fields |
| [`data/edition_location_baseline.csv`](https://github.com/zlat1109/wsdc-data-pipeline/blob/main/data/edition_location_baseline.csv) | Golden edition→location baseline (when editions need a stable lid) |

Raw download (same files): replace `/blob/main/` with `/raw/main/` in the GitHub URL.

**Dashboard extract (same geo the Event Growth UI uses):**

| File | Use |
|------|-----|
| [`static/data/event_growth.json`](https://github.com/wsdc-analytics/wsdc-analytics.github.io/blob/main/static/data/event_growth.json) | `editions[]` rows with city/country/lat/lon/`geo_source` |

Treat **CSV as canonical**; **JSON as the dashboard payload** derived for the site.

## Data dictionary (short)

### `location_info.csv`

| Column | Meaning |
|--------|---------|
| `location_id` | Stable place id |
| `event_city` / `event_state` / `event_country` | Normalized place parts |
| `latitude` / `longitude` | Coordinates |
| `event_location` | Display / raw-ish location string |
| `event_location_standardized` | Standardized label |
| `coordinates_valid` | Flag for usable coordinates |

### `event_editions.csv` (location-related)

| Column | Meaning |
|--------|---------|
| `edition_id` | Edition key |
| `event_id` / `event_name` | Event identity |
| `event_year` / `event_month` | Edition time |
| `location_id` | FK-style link to `location_info` |
| `place_city` / `place_state` / `place_country` | Place on that edition |
| `location_raw` / `typical_location` | Raw / catalog typical strings |

### `event_growth.json` → `editions[]` (geo fields)

| Field | Meaning |
|-------|---------|
| `event_id` / `name` / `year` / `month` | Edition identity |
| `city` / `state` / `country` / `continent` | Place |
| `lat` / `lon` | Coordinates used on the map/charts |
| `city_lat` / `city_lon` | City-level coordinates when present |
| `address` / `hotel` | Venue text when enriched |
| `geo_source` | Provenance (e.g. `wsdc_venue`) |
| `geo_fix` / `approx` | Quality / approximation flags |

## Suggested join

```
event_editions.location_id  →  location_info.location_id
```

For growth UI parity, match `event_growth.json` `editions[]` on `event_id` + `year` + `month` (and name as a check).

## Out of scope here

- Supabase credentials or direct DB access  
- Full parser / CI runbooks  
- Competition Results warehouse design (separate track; we ingest CR as data into our DB when ready — we do not merge scraper repos)

## Related docs

- [Analytics site sync](../operations/analytics-site-sync.md) — how JSON lands on the site  
- [Geography transform](../transform/geography.md) — how places are normalized  
- [Pipeline overview](../architecture/overview.md)

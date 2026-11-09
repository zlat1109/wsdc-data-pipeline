# Event locations — collaborator guide

Cleaned WSDC event locations (geo behind Event Growth / Trends Monitor).  
CSV = source of truth; `event_growth.json` = dashboard extract. Pipeline feeds the analytics site; repos stay separate.

## Live

- [Event Growth (EN)](https://wsdc-analytics.github.io/event_growth_dashboard_en.html)

## Files

| File | Use |
|------|-----|
| [`location_info.csv`](https://github.com/zlat1109/wsdc-data-pipeline/blob/main/data/location_info.csv) | Canonical places: city / state / country + lat/lon |
| [`event_editions.csv`](https://github.com/zlat1109/wsdc-data-pipeline/blob/main/data/event_editions.csv) | Edition → `location_id` + place fields |
| [`edition_location_baseline.csv`](https://github.com/zlat1109/wsdc-data-pipeline/blob/main/data/edition_location_baseline.csv) | Golden edition→location baseline |
| [`event_growth.json`](https://github.com/wsdc-analytics/wsdc-analytics.github.io/blob/main/static/data/event_growth.json) | Dashboard `editions[]` geo payload |

Raw CSV/JSON: in the GitHub URL, replace `/blob/main/` with `/raw/main/`.

Optional schema overview (no credentials): [Database docs](../database/index.md).

## Data dictionary

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
| `location_id` | Link to `location_info` |
| `place_city` / `place_state` / `place_country` | Place on that edition |
| `location_raw` / `typical_location` | Raw / catalog typical strings |

### `event_growth.json` → `editions[]` (geo)

| Field | Meaning |
|-------|---------|
| `event_id` / `name` / `year` / `month` | Edition identity |
| `city` / `state` / `country` / `continent` | Place |
| `lat` / `lon` | Coordinates on the charts |
| `city_lat` / `city_lon` | City-level coordinates when present |
| `address` / `hotel` | Venue text when enriched |
| `geo_source` | Provenance (e.g. `wsdc_venue`) |
| `geo_fix` / `approx` | Quality / approximation flags |

## Join

```
event_editions.location_id  →  location_info.location_id
```

For growth UI parity: `event_id` + `year` + `month` (name as a check).

## Out of scope

- DB credentials / direct Supabase access  
- Full parser / CI runbooks  
- Competition Results warehouse (separate; data ingest later, not repo merge)

# Year Event Calendar

Public analytics page: year grid → day map → event card.

## Data

Built by `scripts/build_year_event_calendar.py` from:

- `edition_calendar_dates.csv` / `event_editions.csv` (day-precision starts + `location_id`)
- `scheduled_events.csv` (confirmed / cancelled / hiatus + Registry|Trial)
- `event_catalog.csv` (url, typical city/country)
- `location_info.csv` (lat/lon when `coordinates_valid`)

Writes `static/data/events_year_calendar.json` on the analytics site (via `--site-repo` or `sync_analytics_site.sh`).

## Status rules

| Status | Meaning |
|--------|---------|
| `confirmed` | Published / scheduled / occurred (day date when known) |
| `stats_only` (flag) | Result-backed edition without day-precision dates: counts in past-year Confirmed, no day-grid pin |
| `has_results` (flag) | `(event_id, year)` has competition `result_rows > 0`; past-year Confirmed on the site uses distinct ids with this flag |
| `expected` | Projected from the **latest confirmed** edition before the target year (±1 week match vs any confirmed start already in that year, WSDC Registry Rules 1.4.1). Anniversary month/day is **snapped to the same weekday** as the prior start (±3 days) so Thu/Fri festivals do not drift onto Mon/Sun by year+2; `end_date` keeps the prior span. Emitted for `as_of.year .. as_of.year + expected_horizon_years` (default: same as `year_radius`, typically current + 2). Skipped when the target year already has confirmed/cancelled/hiatus, or when the series' latest status before the target year is cancelled/hiatus. |
| `cancelled` / `hiatus` | From calendar scrape flags |

Years beyond the expected horizon keep only `scheduled_events` rows (no YoY gray flood from scrape noise). Empty years (no day-precision dates) are omitted from the selector. Inactive/merged catalog ids are not projected. Nameless/`nan` rows are dropped after catalog enrichment.

- Missing `location_id` on schedule rows inherits the latest edition `location_id`, then `location_info` coords (city/country fallback).
- Missing `end_date` inherits duration from another edition of the same `event_id`, else the Sunday of the Thu–Sun weekend containing `start_date`.
- Ghost / inactive duplicate ids are remapped via `MERGE_EVENT_ID_MAP`; remaining same-weekend title variants collapse by name fingerprint (e.g. Boston Tea Party vs The Boston Tea Party).
- **Year-aware series names**: `EVENT_NAME_YEAR_SPLITS` sets display name (and stable results id) by edition year after merge/dedupe — e.g. id `264` is Swedish ≤2018 / UpTown ≥2019; id `221` is Show Me Showdown ≤2025 / Gateway Swing Classic ≥2026 (WSDC id reuse); id `324` is BTO Open ≤2025 / Calgary Town Open ≥2026. Catalog `canonical_name` alone is not trusted for earlier editions.
- **L2 card Points/New**: metrics join `dancers_results_info` by title aliases (`EVENT_NAME_YEAR_SPLITS` + titles seen for the same WSDC id in `events_wsdc.csv`), not only the catalog edition name — so rebrands like Swedish → UpTown still get points/new dancers.
- **UCWDC Worlds**: Dallas series is `75` (`UCWDC Country Dance World Championship`). Catalog `152` (`Worlds UCWDC`) is a separate Orlando-only history (2009/2012/2015). Schedule/calendar titles with “Country Dance World Championship(s)” remapped to `75` even when URL is `ucwdcworlds.com`. Do not merge `152→75`.
- **Registry vs Trial (`kind`)**: live `scheduled_events` Trial flags are trusted; expected YoY rows are always Registry; after a series' first points year, Trial-in-title/catalog does not stick; from **2025+**, first points year (`event_catalog.first_edition_year` / editions with results) marks that year as Trial (heuristic after the registry-points-at-trial rule change).
- Drop `edition_calendar_dates` rows whose `calendar_title` does not match the assigned `event_name` (guards URL mis-matches such as Soul Flow hiatus → Global Grand Prix). Marketing place suffixes that keep the catalog prefix (`WCS Party` → `WCS Party in Vienna`) still match; alias them in `EVENT_NAME_VARIANT_TO_CATALOG` so list scrapes inherit the catalog id and suppress YoY expected. Distinct weekends for the same `event_id`+year are kept separately.
- **Stale expected**: past **event/results years** never keep `expected` (use stub `year` / span end year — not raw `start.year`, so Dec→Jan weekday snaps survive into January). In the current event year, expected rows are dropped once their end date + **7 days** is before `as_of` (projected weekend passed without confirm / hiatus / cancel). Official hiatus/cancelled remain.
- **Provisional unlinked rows**: confirmed list/schedule rows with no `event_id` and year in ``[as_of.year - UNLINKED_PRIOR_LOOKBACK_YEARS, target)`` (default lookback **0**: current year + already-published later list years only) are projected as `expected` **Registry**. Current-year priors must still be upcoming. Old one-off list rows without an id are not resurrected. Operator overrides with synthetic ids (e.g. Soul Flow `990001`) are not covered by this bridge. Series key = name fingerprint (stopwords + edition-year tokens stripped, trailing city dropped) + country.
- Expected YoY also matches confirmed starts across year boundaries (±1 week), so a NYE projection does not ghost when the live schedule moved into early January (e.g. SwingCouver → SwingCo).
- **Series successor suppression** (`SERIES_SUCCESSOR_MAP`): optional expected-skip links when two live registry ids must stay split. Prefer merge + year-aware names (UpTown/Swedish → `264`; Show Me ghosts → `221`) instead of dual-id calendar rows.
- **Operator overrides**: curated gaps (not yet on WSDC calendar/list, or scrape mis-matched) live in `transform/knowledge/calendar_operator_overrides.py`. They are upserted after each calendar sync with `date_source=operator` **and** read directly by the year-calendar builder. Official `wsdc_calendar` for the same `(event_id, year, month)` wins in DB. Examples: Dance Mardi Gras 2026 provisional hiatus (`148`); Soul Flow 2026 hiatus + 2027 expected under provisional id `990001` (WSDC lists Soul Flow under the old Toulouse GGP URL — do not merge into `342`).
- **Year of event** = results/`event_year` (not always `start_date.year`). Cross-year weekends (Dec → Jan) stay in the results year; the day grid only paints ISO days that fall in the selected year.
- **Missing day dates** with results: emit `stats_only` from `event_editions` (placeholder `edition_date`); exclude from YoY expected priors; site skips day cells. Drop a `stats_only` row when the same `event_id`+year already has a day-precision calendar/schedule row (month placeholder vs real weekend).
- **Scheduled / calendar rows** carry `year` from `results_year` / `event_year` when present.

Each event includes `continent` in `{America, Europe, Asia, Australia}` (South America → America).

## Spike

```bash
python scripts/build_year_event_calendar.py --data-dir data --spike 2025 2026
```

## Site

- Page: `events-calendar.html` (EN/RU/ES)
- Refresh: `scripts/sync_analytics_site.sh` after full-parse export

# Event Editions enrichment (Todd Analytical Datasets)

Parallel layer for attributes Todd publishes that **`core.event_editions` does not**:
registry status, scoring software, venue, metro, Results Form officials, and a
history of cancelled / hiatus / no_results editions.

Does **not** replace `core.event_editions`, `core.locations`, or
`core.scheduled_events`. Non-WSDC Todd rows are skipped.

## Inputs (local only)

| Input | Notes |
|-------|--------|
| `Event Editions/event_editions.parquet` | Path via `--ee-path` or `EE_PATH` |
| `export_manifest.json` (sidecar) | Optional `built_at` / `git_commit` for `ee_loads` |
| `data/reference/event_editions_decisions.yaml` | Blocking gate allowlist |

## Tables

| Table | Grain |
|-------|--------|
| `core.ee_loads` | One load audit row |
| `core.edition_attributes` | Occurred WSDC edition attrs on `(event_id, year, month)` |
| `core.edition_status_history` | cancelled / hiatus / no_results |
| `core.metros` | Metro area dim |
| `core.venues` | Deduped venues |
| `core.officials` | People dim (Results Form names) |
| `core.edition_officials` | Edition × official bridge |

`core.locations.metro_id` is backfilled from Todd city→metro mapping.
`core.cr_judge_marks.official_id` is soft-linked by normalized judge name.

Natural keys only — **no FK** into `core.event_editions` (weekly promote
`TRUNCATE … CASCADE`). Same pattern as Competition Results (migration 040).

## Source of truth

- Occurred edition dates / city / existence → **`core.event_editions`**
- Future schedule → **`core.scheduled_events`**
- Todd fills **new** columns only; value conflicts require a decisions.yaml case
  (gate blocks `--apply` otherwise)

## Load

```bash
# Plan only
python scripts/load_event_editions.py \
  --ee-path ~/Downloads/"Analytical Datasets"/"Event Editions"/event_editions.parquet \
  --dry-run

# Full layer (attrs + status + metros/venues + officials)
python scripts/load_event_editions.py \
  --ee-path … --apply --migrate \
  --with-metros-venues --with-officials

# Live soft-FK probes
python scripts/load_event_editions.py --check-conflicts
```

`--apply` truncates the EE enrichment tables (and clears `locations.metro_id` /
`edition_attributes.venue_id` when metros/venues are included), then reloads in
one session. It never truncates `core.event_editions` / `core.results`.

Report: `data/quality_reports/event_editions_recon.json`.

## Export

| View / CSV | File |
|------------|------|
| `export.edition_attributes` | `edition_attributes.csv` |
| `export.edition_status_history` | `edition_status_history.csv` |
| `export.metros` | `metros.csv` |
| `export.venues` | `venues.csv` |
| `export.officials` | `officials.csv` |
| `export.edition_officials` | `edition_officials.csv` |

## After promote / new Todd zip

See the end-to-end refresh checklist:
[todd-analytical-datasets.md](todd-analytical-datasets.md).

Re-apply `--with-metros-venues` after weekly `promote_core` (clears
`locations.metro_id`).

## Related

- [todd-analytical-datasets.md](todd-analytical-datasets.md) — CR + EE refresh when Todd ships a new zip
- [competition-results.md](competition-results.md) — CR scrape layer (join on Todd `event_edition_id` ≈ `cr_edition_id`)
- [quality-monitoring.md](quality-monitoring.md)
- [../database/core.md](../database/core.md)

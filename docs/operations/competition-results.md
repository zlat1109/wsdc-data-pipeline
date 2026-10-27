# Competition Results enrichment (`core.cr_*`)

Parallel scrape layer for data that **WSDC public results do not publish**: prelims / quarters / semis, unscored finalists, partners, judge marks, and other divisions (Strictly, Masters, fun, …).

Does **not** replace or mutate `core.results`, `core.dancers`, or `core.event_editions`. Nullable FKs only — unknown dancers stay `dancer_id NULL` with raw `cr_identity`.

## Inputs (local only)

| Input | Notes |
|-------|--------|
| Competition Results `results.parquet` | Path via `--cr-path` or `CR_RESULTS_PATH` |
| `core.event_editions` / `core.dancers` | Read for matching; never written by this loader |

Sources stay on disk. Only the load script writes to Supabase.

## What is loaded

Kept when `event_edition_id` starts with `wsdc:` **and** `result_from_other_source` is true.

Dropped:

- non-WSDC events (`eepro:…`, `non_wsdc_event`);
- pure WSDC public copies (`result_from_wsdc` without scrape).

Scored placements and points remain in `core.results`. CR finals that also appear in WSDC public results are still stored in `cr_*` as the scrape layer (partners / marks); join them via `export.cr_finals_vs_scored`.

## Tables

| Table | Grain |
|-------|--------|
| `core.cr_loads` | One load audit row |
| `core.cr_editions` | CR edition (`wsdc:<id>:<Month YYYY>`) ↔ nullable `edition_id` |
| `core.cr_divisions` | Per-edition division (`raw_division` + `level` / `category` / `label`) |
| `core.cr_rounds` | prelim / quarter / semi / final |
| `core.cr_round_results` | One competitor per round |
| `core.cr_final_couples` | Finals: one couple (judge ranks the pair) |
| `core.cr_judge_marks` | Long form: per competitor (prelim…) or per couple (final) |

Column inventory: [../database/_generated/tables.md](../database/_generated/tables.md). Narrative: [../database/core.md](../database/core.md#competition-results-enrichment-corecr_).

## Export views (Supabase only — not in `export.py` CSV)

| View | Purpose |
|------|---------|
| `export.cr_editions` | Editions + matched event calendar fields |
| `export.cr_round_results` | Flat competitor rows with division / event |
| `export.cr_judge_marks` | Long-form marks |
| `export.cr_finals_vs_scored` | CR finals LEFT JOIN `core.results` (`unscored_finalist`) |

## Load

```bash
# Plan only (writes data/quality_reports/cr_load_report.json)
python scripts/load_competition_results.py \
  --cr-path ~/Downloads/"Competition Results"/results.parquet --dry-run

# Apply migration if needed, then full replace of core.cr_*
python scripts/load_competition_results.py \
  --cr-path ~/Downloads/"Competition Results"/results.parquet --apply --migrate

# Live FK / identity conflict probes (no load)
python scripts/load_competition_results.py --check-conflicts
```

`--apply` truncates all `core.cr_*` data tables and reloads in one transaction, then runs live conflict checks. It never `COPY`/`TRUNCATE`s `core.results` / `core.dancers` / `core.event_editions`.

### Weekly promote hazard (fixed in migration 040)

`db/sql/promote_core.sql` runs `TRUNCATE core.dancers, core.events, … RESTART IDENTITY CASCADE`. Any **DB FK** from `cr_*` into those tables caused Postgres to wipe `cr_editions` / `cr_round_results` / … while leaving `cr_loads` audit rows. Symptom: `cr_loads` > 0, all other `cr_*` = 0.

Mitigation: soft references only (no FK to `dancers` / `event_editions`); promote nulls `cr_editions.edition_id` before truncate. After a promote, rematch with `--apply` (or a future rematch-only path). Conflict probes still enforce orphans.

## Conflict gates

Offline (during dry-run/apply) + live SQL:

- orphan `dancer_id` / `partner_dancer_id` / `edition_id` / `level`
- `dancer_id` ≠ numeric `cr_identity`
- matched edition’s `canonical_event_id` ≠ `core.event_editions.event_id`
- redacted identity must not store a name

Also registered in [quality-monitoring.md](quality-monitoring.md) (`category=competition_results`).

## Code map

| Path | Role |
|------|------|
| `transform/competition_results/` | Filters, edition match, divisions, couples, marks, conflict probes |
| `scripts/load_competition_results.py` | Dry-run / apply / `--check-conflicts` |
| `db/migrations/039_competition_results.sql` | DDL + export views + RLS |
| `scripts/build_event_data_completeness_report.py` | Local Event Data Registry HTML (uses same side-label helpers) |

## Event Data Registry (analytics site)

Internal unlisted page built locally from the same parquet + dump TSVs + Results Forms:

```bash
python scripts/build_event_data_completeness_report.py \
  --cr-path ~/Downloads/"Competition Results"/results.parquet \
  --site-repo ~/.cursor/wsdc-analytics-repo
```

Publishes `internal/event-data-registry.html` (`noindex`, `robots.txt` Disallow `/internal/`). Manual refresh until CR lives fully in the site pipeline. See [analytics-site-sync.md](analytics-site-sync.md).

## Related

- Dump headcounts (different source): [mysql-dump-reload.md](mysql-dump-reload.md), `load_competitions_from_dump.py`
- [quality-monitoring.md](quality-monitoring.md)
- [../database/export-views.md](../database/export-views.md)

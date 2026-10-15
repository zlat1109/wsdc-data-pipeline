# MySQL dump reload (exact headcounts + edition dates)

**When:** a new Navicat/RDS dump arrives (e.g. `wsdcMMDDYY.sql`) and you need
exact L/F competition headcounts and/or dump day-dates on the calendar.

**Not covered by full-parse.** Cloud parse does **not** reload `core.competitions`.
Without this runbook, L2 Dancers fall back to tier estimates (`~`).

Quick commands only: `dumps/README.md` (repo root; not part of MkDocs).  
Site push details: [analytics-site-sync.md](analytics-site-sync.md).  
Script internals: [load_competitions_from_dump.py](repair-scripts.md#load_competitions_from_dumppy),
[sync_dump_edition_dates.py](repair-scripts.md#sync_dump_edition_datespy).

---

## What this updates

| Layer | Effect |
|-------|--------|
| Docker `wsdc-clone` | Full MySQL clone replaced by the new dump |
| `core.competitions` | Exact WCS L/F/finals from dump (matched to editions) |
| `core.edition_calendar_dates` / editions | Day dates from `competitionevents` (`date_source=wsdc_dump`) where we still had month stubs |
| `data/competitions_best.csv` (+ related export) | Deduped headcounts for analytics |
| Analytics site | Year calendar L2 cards, Event tiers, KPIs, TID, secondary-role (via force-rebuild) |

Point Summary / Champion News usually **do not** change from a dump-only reload
(they follow points cutoff windows, not competitions TSV).

---

## Prerequisites

1. Docker container **`wsdc-clone`** running (DB `wsdc`, port `3306`, password in
   container env `MYSQL_ROOT_PASSWORD`).
2. Local pipeline venv + `.env` / secrets for **Supabase** (same as export).
3. Dump file on disk (typically `~/Downloads/wsdcMMDDYY.sql`).
4. Optional: note 1–2 events that should appear with exact dancers (sanity check).

```bash
docker ps --filter name=wsdc-clone
# run remaining commands from this repo root
```

---

## Checklist (copy/paste)

### 1) Place dump

```bash
cp ~/Downloads/wsdcMMDDYY.sql dumps/
# optional: keep one previous dump renamed, e.g. dumps/wsdc_prev.sql
```

`dumps/wsdc*.sql` and extracted `*.tsv` are **gitignored**. Do not commit the dump.

### 2) Load into Docker MySQL

MySQL 8 rejects dump `0000-00-00` dates unless `ALLOW_INVALID_DATES` is set:

```bash
docker cp dumps/wsdcMMDDYY.sql wsdc-clone:/tmp/wsdc.sql
docker exec wsdc-clone bash -c '
  mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 wsdc \
    --init-command="SET SESSION sql_mode=\"ALLOW_INVALID_DATES,NO_ENGINE_SUBSTITUTION\"" \
    < /tmp/wsdc.sql
'
docker exec wsdc-clone rm -f /tmp/wsdc.sql
```

Smoke:

```bash
docker exec wsdc-clone bash -c '
  mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N -e \
    "SELECT COUNT(*) FROM wsdc.competitions; SELECT COUNT(*) FROM wsdc.competitionevents;"
'
```

### 3) Dry-run, then apply competitions + dates

Run **competitions load first**: it extracts both TSVs. Dates sync reads
`dumps/competitionevents_dates.tsv` and fails if that file is missing.

```bash
python scripts/load_competitions_from_dump.py --dry-run
python scripts/load_competitions_from_dump.py --apply

python scripts/sync_dump_edition_dates.py --dry-run
python scripts/sync_dump_edition_dates.py --apply --export --build-year-calendar
```

`--apply` on competitions writes `dumps/competitions_wcs.tsv` +
`dumps/competitionevents_dates.tsv` and upserts Supabase.

Reports:

- `data/quality_reports/competitions_load.json`
- `data/quality_reports/dump_edition_dates_report.json` (+ `.csv`)

If dates were applied without `--export`, run:

```bash
python export.py --output-dir data
python scripts/build_year_event_calendar.py --data-dir data
```

### 4) Quality gates (local)

```bash
python scripts/monitor_data_quality.py
# expect competitions_matched_floor OK (≥10k matched rows)
```

Spot-check known editions (adjust the name substring / year):

```bash
python - <<'PY'
import pandas as pd
c = pd.read_csv("data/competitions_best.csv")
print("competitions_best rows:", len(c))
q = c[
    c["event_name"].astype(str).str.contains("Norwegian", case=False, na=False)
    & (c["event_year"].astype(str) == "2026")
]
print(
    q.groupby("event_name", as_index=False)
    .agg(L=("leader_count", "sum"), F=("follower_count", "sum"), rows=("level", "count"))
    .to_string(index=False)
)
print("Σ(L+F) skill:", int(q["leader_count"].fillna(0).sum() + q["follower_count"].fillna(0).sum()))
PY
```

On L2 cards after site sync: `unique_dancers` = exact Σ(L+F) skill levels,
`dancers_approx: 0` means exact (not tier fallback).

### 5) Ship CSVs + site

**Preferred (CI):** after Supabase is updated, dispatch on `main`:

Actions → **Force rebuild calendar/site** (`force-rebuild-calendar-site.yml`)

- Exports Supabase → `data/*.csv`
- Commits CSVs to `main` (if `commit_csv=true`)
- Runs `sync_analytics_site.sh` → pushes
  [wsdc-analytics.github.io](https://wsdc-analytics.github.io/)

**Local alternative:** commit refreshed export CSVs yourself, then either push
and run force-rebuild, or run `bash scripts/sync_analytics_site.sh` with
`WSDC_ANALYTICS_DEPLOY_TOKEN` (see [analytics-site-sync.md](analytics-site-sync.md)).

Do **not** push dump SQL or `dumps/*.tsv`.

### 6) Verify live site

| Section | URL / file |
|---------|------------|
| Year Event Calendar + L2 | https://wsdc-analytics.github.io/events-calendar.html |
| Event tiers by year | https://wsdc-analytics.github.io/event_tiers_by_year_dashboard_en.html |
| Homepage KPIs | https://wsdc-analytics.github.io/ |
| Time in Division | https://wsdc-analytics.github.io/time_in_division_dashboard_en.html |
| Secondary role | https://wsdc-analytics.github.io/secondary_role_distribution_dashboard_en.html |

Checks:

1. Force-rebuild run green; analytics commit message mentions rebuild / `as_of` = today.
2. Target event L2: exact dancer count, not `~`.
3. Hard refresh (Cmd+Shift+R) if Pages CDN looks stale.

---

## Flow diagram

```
new wsdc*.sql
  → docker cp + mysql (ALLOW_INVALID_DATES) → wsdc-clone
  → load_competitions_from_dump.py --apply     → core.competitions
  → sync_dump_edition_dates.py --apply
       --export --build-year-calendar         → dates + local data/*.csv
  → Force rebuild calendar/site                 → commit CSV + Pages
```

---

## Failure modes

| Symptom | Cause | Fix |
|---------|-------|-----|
| Import errors on dates / `0000-00-00` | MySQL 8 strict sql_mode | Re-run step 2 with `ALLOW_INVALID_DATES` |
| `docker mysql failed` / container missing | `wsdc-clone` not up | Start/recreate clone; see dumps README |
| L2 still shows `~` dancers | Empty or wiped `core.competitions` / stale export | Re-run load `--apply`; force-rebuild; check `competitions_matched_floor` |
| Export refuses overwrite / gate fail | Non-empty CSV would become 0 rows | Do not wipe competitions; reload dump first |
| High unmatched in `competitions_load.json` | Edition not in registry / MERGE gap | Investigate `edition_id NULL` rows; may need catalog/merge repair |
| Day≠day in dump dates report | Dump vs existing day-precision conflict | Manual review only (script does not overwrite) |
| Site unchanged after apply | Forgot force-rebuild / token | Dispatch force-rebuild; confirm `WSDC_ANALYTICS_DEPLOY_TOKEN` (org `wsdc-analytics`) |
| PR only touching `dumps/README.md` | Path filter runs pytest | Expected; keep README + tests green |

---

## Docs touchpoints (optional)

If the dump procedure itself changes (new flags, container name, gates), update
in the same PR:

1. This runbook
2. `dumps/README.md` (short commands at repo root)
3. [repair-scripts.md](repair-scripts.md) dump sections if CLI changes

Editing `dumps/README.md` triggers the Tests workflow path filter — run or rely
on CI pytest for dump-related unit tests.

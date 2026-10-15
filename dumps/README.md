# Local extracts for dump sync (gitignored)

**Full runbook (checklist → site):**
[docs/operations/mysql-dump-reload.md](../docs/operations/mysql-dump-reload.md)

## Full MySQL dump → Docker `wsdc-clone`

Navicat/RDS dump (e.g. `wsdc101526.sql`) lives here as `dumps/wsdc*.sql` (gitignored).

```bash
# 1) Place dump
cp ~/Downloads/wsdcMMDDYY.sql dumps/

# 2) Load into existing container (MySQL 8 rejects 0000-00-00 without this sql_mode)
docker cp dumps/wsdcMMDDYY.sql wsdc-clone:/tmp/wsdc.sql
docker exec wsdc-clone bash -c '
  mysql -uroot -p"$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 wsdc \
    --init-command="SET SESSION sql_mode=\"ALLOW_INVALID_DATES,NO_ENGINE_SUBSTITUTION\"" \
    < /tmp/wsdc.sql
'
docker exec wsdc-clone rm -f /tmp/wsdc.sql

# 3) Re-extract TSVs + upsert Supabase competitions (+ optional dates/calendar)
python scripts/load_competitions_from_dump.py --apply
python scripts/sync_dump_edition_dates.py --apply --export --build-year-calendar

# 4) Ship site: Actions → Force rebuild calendar/site
```

Container defaults: name `wsdc-clone`, DB `wsdc`, password from container env
`MYSQL_ROOT_PASSWORD`, host port `3306`.

## competitionevents dates

Non-PII slice from WSDC MySQL clone `competitionevents`:

```text
id \t event_id \t event_name \t start_date \t end_date
```

- `id` = per-edition PK (not our registry id)
- `event_id` = series registry id (= our `core.events.event_id` before MERGE)

```bash
mkdir -p dumps
docker exec wsdc-clone bash -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" wsdc \
  --default-character-set=utf8mb4 -N -B -e \
  "SELECT id, event_id, IFNULL(event_name,\"\"), IFNULL(start_date,\"\"), IFNULL(end_date,\"\") \
   FROM competitionevents"' \
  > dumps/competitionevents_dates.tsv

python scripts/sync_dump_edition_dates.py --dry-run
python scripts/sync_dump_edition_dates.py --apply --export --build-year-calendar
```

## competitions (exact headcounts, WCS)

```bash
python scripts/load_competitions_from_dump.py --dry-run
python scripts/load_competitions_from_dump.py --apply
```

Writes `dumps/competitions_wcs.tsv` (gitignored) and upserts `core.competitions`.
Match reuses dump edition logic (`competitionevents` → `event_editions`).
Unmatched rows are kept with `edition_id NULL` for investigation.
For headcounts in analytics use `export.competitions_best` (deduped).

**Ops note:** full-parse does **not** reload competitions. If `core.competitions`
is wiped, the next export writes an empty `competitions_best.csv` and calendar
L2 Dancers falls back to tier estimates (`~`). Guards:
export refuses to overwrite a non-empty CSV with 0 DB rows; export-vs-DB gate
requires ≥10k competitions_best rows; quality check `competitions_matched_floor`.

See [repair-scripts.md](../docs/operations/repair-scripts.md#sync_dump_edition_datespy).

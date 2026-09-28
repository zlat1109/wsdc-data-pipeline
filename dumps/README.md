# Local extracts for dump sync (gitignored)

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

See [repair-scripts.md](../docs/operations/repair-scripts.md#sync_dump_edition_datespy).

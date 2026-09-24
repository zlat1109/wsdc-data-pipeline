# Local extract for dump date sync (gitignored)

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

See [repair-scripts.md](../docs/operations/repair-scripts.md#sync_dump_edition_datespy).

# Events list (schedule scrape)

Weekly scrape of https://www.worldsdc.com/events/ — independent from points parse/load.

## vs points registry

| Aspect | Points (`core.events`) | Schedule (`events_list_current`) |
|--------|------------------------|----------------------------------|
| Source | points.worldsdc.com API | worldsdc.com HTML scrape |
| Update | Weekly full parse | Tuesday sync |
| Names | Historical catalog titles | Current marketing names |
| Link | `canonical_event_id` after mapping | FK to `core.events` |

Points load does **not** truncate schedule tables.

## Storage

| Table | Grain |
|-------|-------|
| `core.scheduled_events` | Edition archive (all fingerprints) |
| `core.events_list_current` | One row per brand (nearest date) |
| `history.events_list_runs` | Scrape run metadata |
| `history.events_list_changes` | Added/removed log |

## Export views

| View | Use |
|------|-----|
| `export.scheduled_events` | Default CSV — one row per event |
| `export.scheduled_event_editions` | All active future editions |
| `export.scheduled_events_legacy` | Deprecated edition shape |

See [../tableau/dashboards-migration.md](../tableau/dashboards-migration.md).

## Repo artifacts

`data/events_list/`:

- `current.json`, `events_list.csv`
- `changelog/latest.json`, `changelog/run_*.json`
- `mapping/latest.json` — mapping analysis

## Commands

```bash
python scripts/sync_events_list.py
python scripts/analyze_events_list_mapping.py
```

CI: `.github/workflows/sync-events-list.yml` — Tuesday 08:00 UTC.

## Mapping pipeline

1. Scrape → normalize (`transform/events_list_normalize.py`)
2. Match to catalog (`transform/events_list_mapping.py`, `parser/event_name_matcher.py`)
3. Write `match_status`, `canonical_event_id` on `events_list_current`

Report sections in `mapping/latest.json`:

| Section | Meaning |
|---------|---------|
| `confirmed` | Strong match |
| `manual_review_required` | Fuzzy or location drift |
| `new_events` | Not in points catalog |
| `location_drifts` | Same event, different location string |

## Event renames

When schedule shows new brand but points still use old title → add alias in `parser/event_name_matcher.py`, not rename `core.events.name`.

See [../policies/event-rename-aliases.md](../policies/event-rename-aliases.md).

## Related

- [../database/core.md](../database/core.md) — schedule table fields
- [../operations/github-actions.md](../operations/github-actions.md) — sync workflow

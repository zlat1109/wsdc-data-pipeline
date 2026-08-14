# Point Summary (pipeline-owned)

Point Summary entities on
[points-summary.html](https://wsdc-analytics.github.io/points-summary.html)
are built by **wsdc-data-pipeline** after each full parse / export. The Telegram
bot only posts links to entities that already exist on the site.

## Entity model

| Field | Meaning |
|---|---|
| `slug` | `{start_date}-{event-name}` (stable edition key) |
| `post_date` | Date the pipeline **first created** the entity (`DD-MM-YYYY`) |
| Create rule | `start_date >= POINT_SUMMARY_CUTOFF` and at least one division with places 1–3 |
| Update window | 30 days after `end_date`; slug + `post_date` never change |
| `telegraph_url` | Optional; bot may patch it later without rewriting the body |

Cutoff default: **2026-07-28** (`POINT_SUMMARY_CUTOFF`). Historical blocks in
`points_summaries.json` are not **created** before cutoff. Existing blocks
inside the 30-day update window are rebuilt, but `[N]` registry totals and
🟡/🟢 markers are **as of that edition's start date** (later results are
subtracted from the live CSV snapshot). Do not copy today's totals onto
older cards.

## Builder

```bash
python scripts/build_points_summary.py \
  --data-dir data \
  --site-repo /tmp/wsdc-site \
  --cutoff 2026-07-28 \
  --update-window-days 30 \
  --report data/quality_reports/point_summary_last.json
```

When `event_editions.start_date` is blank (common for month-level WSDC list
rows), the builder fills dates from `scheduled_events.csv` for the same
`event_id` / name + year/month so trial events like Infinite Swing still get a
stable `{start_date}-…` slug.

Modules:

- `transform/knowledge/geo_flags.py` — continent / flag from `place_country`
- `transform/points_summary/` — Chart 3 markers, podium overrides, report + merge
- Merge preserves unknown fields (especially `telegraph_url`)

## CI

`scripts/sync_analytics_site.sh` (from `full-parse.yml`):

1. Clones analytics site
2. Rebuilds homepage KPIs + secondary dashboard
3. Runs `build_points_summary.py` (failure → warning, does not abort KPI sync)
4. Commits `static/data/points_summaries.json` with the other JSON files
5. `#WSDC_Pipeline_Complete` includes `Point Summary: +N` when the report exists

## Local dry-run

```bash
python scripts/build_points_summary.py \
  --data-dir data \
  --existing ~/.cursor/wsdc-analytics-repo/static/data/points_summaries.json \
  --output /tmp/points_summaries.json \
  --cutoff 2026-07-28 \
  --dry-run
```

## Tests

`tests/test_points_summary.py` — unit checks for slug/geo/merge + golden podium
composition against recent live `points_summaries.json` (names and `(+N)` points;
running totals in `[]` are allowed to drift).

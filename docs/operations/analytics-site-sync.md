# Analytics site sync (homepage KPIs + secondary-role + Point Summary)

After each successful `full-parse.yml` export, the pipeline rebuilds JSON for
[wsdc-analytics.github.io](https://wsdc-analytics.github.io/) and pushes it.

## What gets updated

| Site surface | File | Builder |
|---|---|---|
| Homepage counters (events / points / dancers) | `static/data/homepage_kpis.json` | analytics `scripts/build_homepage_kpis.py` |
| Secondary-role country dashboard | `static/data/secondary_country_unified.json` | analytics `scripts/update_secondary_country_unified.py` |
| Point Summary catalog | `static/data/points_summaries.json` | pipeline `scripts/build_points_summary.py` |
| Champion News chronology | `static/data/champion_news.json` | pipeline `scripts/build_champion_news.py` |
| Year Event Calendar | `static/data/events_year_calendar.json` | pipeline `scripts/build_year_event_calendar.py` |

Live:
- https://wsdc-analytics.github.io/index.html?lang=en
- https://wsdc-analytics.github.io/secondary_role_distribution_dashboard_en.html
- https://wsdc-analytics.github.io/points-summary.html
- https://wsdc-analytics.github.io/champion-news.html
- https://wsdc-analytics.github.io/events-calendar.html

See also [point-summary.md](point-summary.md), [champion-news.md](champion-news.md), and [year-event-calendar.md](year-event-calendar.md).

## Secret (this repo)

| Secret | Purpose |
|---|---|
| `WSDC_ANALYTICS_DEPLOY_TOKEN` | PAT with **Contents: Read and write** on `wsdc-analytics/wsdc-analytics.github.io` |

Same token family as the bot's analytics deploy secret is fine if it can write to the site repo.

## Flow

```
full-parse.yml / sync-events-list.yml / force-rebuild-calendar-site.yml
  → export.py (data/*.csv)   [force-rebuild: export-only]
  → commit CSV (optional; list-sync may skip if no diff)
  → sync_analytics_site.sh
       clone analytics site
       build homepage_kpis.json + secondary_country_unified.json from data/
       build/merge points_summaries.json (cutoff + 30d window; warn-on-fail)
       build champion_news.json (warn-on-fail)
       build events_year_calendar.json + event_l2_cards.json
         (REQUIRE_YEAR_CALENDAR=1 → hard fail; no silent stale calendar)
       stamp calendar/dashboard ?v= cache buster
       validate_site_data.py
       commit + push → GitHub Pages
  → Telegram #WSDC_Pipeline_Complete (+ location mismatch cards when findings exist)
```

**Force rebuild after manual DB location repair:** Actions → **Force rebuild calendar/site**
(`force-rebuild-calendar-site.yml`). Sets `REQUIRE_DEPLOY_TOKEN=1` and
`REQUIRE_YEAR_CALENDAR=1`.

Env flags for `sync_analytics_site.sh`:

| Env | Default | Meaning |
|-----|---------|---------|
| `REQUIRE_DEPLOY_TOKEN` | `0` | `1` → missing PAT fails the job (full-parse / force-rebuild) |
| `REQUIRE_YEAR_CALENDAR` | `1` | `1` → calendar build failure exits non-zero |

## Local paths

| Repo | Path |
|---|---|
| Pipeline | `~/.cursor/projects/python/wsdc-data-pipeline` |
| Analytics site | `~/.cursor/wsdc-analytics-repo` (`wsdc-analytics/wsdc-analytics.github.io`) |

Local rebuild (no CI):

```bash
PIPE=~/.cursor/projects/python/wsdc-data-pipeline/data
SITE=~/.cursor/wsdc-analytics-repo

python3 "$SITE/scripts/build_homepage_kpis.py" \
  --source-dir "$PIPE" --output "$SITE/static/data/homepage_kpis.json"

python3 "$SITE/scripts/update_secondary_country_unified.py" \
  --source-dir "$PIPE" --output "$SITE/static/data/secondary_country_unified.json"

python3 ~/.cursor/projects/python/wsdc-data-pipeline/scripts/build_points_summary.py \
  --data-dir "$PIPE" --site-repo "$SITE" --cutoff 2026-07-28

python3 ~/.cursor/projects/python/wsdc-data-pipeline/scripts/build_champion_news.py \
  --data-dir "$PIPE" --site-repo "$SITE" --cutoff 2026-07-25

cd "$SITE" && python3 scripts/validate_site_data.py
# then commit static/data/*.json and push main → Pages
```

## Manual CI-style run

```bash
export WSDC_ANALYTICS_DEPLOY_TOKEN='ghp_...'
bash scripts/sync_analytics_site.sh
```

## Extending later (articles)

Article HTML under the analytics repo can get similar rebuild steps once generators
are stable; keep them behind the same script or a sibling `sync_analytics_articles.sh`.

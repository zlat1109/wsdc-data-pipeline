# Analytics site sync (homepage KPIs + secondary-role dashboard)

After each successful `full-parse.yml` export, the pipeline rebuilds JSON for
[wsdc-analytics.github.io](https://wsdc-analytics.github.io/) and pushes it.

## What gets updated

| Site surface | File | Builder (in analytics repo) |
|---|---|---|
| Homepage counters (events / points / dancers) | `static/data/homepage_kpis.json` | `scripts/build_homepage_kpis.py` |
| Secondary-role country dashboard | `static/data/secondary_country_unified.json` | `scripts/update_secondary_country_unified.py` |

Live:
- https://wsdc-analytics.github.io/index.html?lang=en
- https://wsdc-analytics.github.io/secondary_role_distribution_dashboard_en.html

`points_summaries.json` is still updated by **wsdc-telegram-bot** results runs (separate flow).

## Secret (this repo)

| Secret | Purpose |
|---|---|
| `WSDC_ANALYTICS_DEPLOY_TOKEN` | PAT with **Contents: Read and write** on `wsdc-analytics/wsdc-analytics.github.io` |

Same token family as the bot's analytics deploy secret is fine if it can write to the site repo.

## Flow

```
full-parse.yml
  → export.py (data/*.csv)
  → commit CSV (optional)
  → sync_analytics_site.sh
       clone analytics site
       build homepage_kpis.json + secondary_country_unified.json from data/
       validate_site_data.py
       commit + push → GitHub Pages
```

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

cd "$SITE" && python3 scripts/validate_site_data.py
# then commit static/data/*.json and push main → Pages
```

## Manual CI-style run

```bash
export WSDC_ANALYTICS_DEPLOY_TOKEN='ghp_...'
bash scripts/sync_analytics_site.sh
```

Local build only (no push):

```bash
python /path/to/wsdc-analytics-repo/scripts/build_homepage_kpis.py --source-dir data
python /path/to/wsdc-analytics-repo/scripts/update_secondary_country_unified.py --source-dir data
```

## Extending later (articles)

Article HTML under the analytics repo can get similar rebuild steps once generators
are stable; keep them behind the same script or a sibling `sync_analytics_articles.sh`.

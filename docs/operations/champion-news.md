# Champion News (pipeline-owned)

Champion News entities on
[champion-news.html](https://wsdc-analytics.github.io/champion-news.html)
are built by **wsdc-data-pipeline** after each full parse / export (warn-on-fail).

v1: page is on the site but **not** linked from chrome/homepage — use the direct URL.
Telegram Champion News stays a separate manual RU editorial workflow.

## Milestones

| Status | Rule |
|---|---|
| Allowed | cumulative All-Stars ≥ 150 (per dancer × role) |
| Required | cumulative All-Stars ≥ 225 **or** Champions ≥ 10 |

Roles: `leader` and `follower` are tracked separately (up to four cards per dancer).

If both Required paths are crossed in the **same edition**, the recorded pathway is
`als_225` (All-Stars checked first). Champions-only Required without prior Allowed
is possible when CHMP ≥ 10 while ALS < 150.

## Entity model

File: `static/data/champion_news.json`

```text
{ "summaries": [ {
    post_date, events_count,
    events: [{
      slug, title, dancer_id, dancer_name, role,
      status, required_pathway,
      threshold_date, threshold_event, threshold_location,
      als_total, chmp_total, flag, continent,
      path: { first_points, first_all_stars, event_counts, top_*, continents_* },
      notes?, overrides?
    }]
} ] }
```

Slug: `{threshold_date}-{dancer_id}-{role}-{allowed|required}`

Create rule: `threshold_date >= CHAMPION_NEWS_CUTOFF` (default **2026-07-28**).
Merge refreshes auto fields and **preserves** `notes` / `overrides`.

`path` is computed **as of the block `post_date`** (publication snapshot), not
today. Each card also stores `path_as_of` (ISO date). Rebuild refreshes every
existing card's path with that freeze date so archive cards do not pick up
later editions.

## Builder

```bash
python scripts/build_champion_news.py \
  --data-dir data \
  --site-repo /tmp/wsdc-site \
  --cutoff 2026-07-28 \
  --report data/quality_reports/champion_news_last.json
```

Modules: `transform/champion_news/` (`detect`, `path`, `merge`, `thresholds`).

## CI

`scripts/sync_analytics_site.sh` runs the builder after Point Summary.
`#WSDC_Pipeline_Complete` includes a Champion News line when the report exists.

## Archive

Historical Telegram posts are **out of scope for v1**. Later: CSV backfill with a separate cutoff.

## Related

- [analytics-site-sync.md](analytics-site-sync.md)
- Bot manual workflow: `telegram-news-bot/docs/CHAMPION_NEWS_MANUAL_WORKFLOW.md`

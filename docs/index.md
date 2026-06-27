# WSDC Data Pipeline — Documentation

English reference for the World Swing Dance Championships data pipeline: parser → Supabase → CSV export → Tableau Public.

!!! tip "Web site"
    Browse with search and navigation: **[zlat1109.github.io/wsdc-data-pipeline](https://zlat1109.github.io/wsdc-data-pipeline/)**  
    Local preview: `pip install -r requirements-docs.txt && mkdocs serve`

## Who should read what

| I am… | Start here |
|-------|------------|
| **Tableau analyst** | [Tableau overview](tableau/index.md) → [CSV contract](tableau/csv-contract.md) → [Joins](tableau/joins.md) |
| **Developer / maintainer** | [Pipeline overview](architecture/overview.md) → [Database](database/index.md) → [Transform](transform/index.md) |
| **Ops / on-call** | [Operations](operations/index.md) |

## Documentation map

### Architecture

- [Pipeline overview](architecture/overview.md) — End-to-end stages and entry points
- [Event identity](architecture/identity-model.md) — `event_id`, editions, `geo_event_key`
- [SCD2 history](architecture/scd2-history.md) — Points and roles change tracking

### Database (Supabase / Postgres)

- [Schema overview](database/index.md) — ER diagrams
- [Staging](database/staging.md) — Parser CSV landing zone
- [Core](database/core.md) — Normalized current state
- [History](database/history.md) — Run journal and SCD2 tables
- [Export views](database/export-views.md) — Tableau-facing SQL views
- [Migrations](database/migrations.md) — Migration index and `apply.py`

### Transform & normalization

- [Transform overview](transform/index.md) — Preprocess pipeline
- [Divisions & levels](transform/divisions-levels.md)
- [Geography](transform/geography.md)
- [Event names](transform/event-names.md)
- [Events list](transform/events-list.md)

### Tableau

- [Tableau overview](tableau/index.md) — Weekly refresh workflow
- [CSV contract](tableau/csv-contract.md) — Column catalog
- [Joins](tableau/joins.md)
- [Schedule migration](tableau/dashboards-migration.md)

### Operations

- [Operations index](operations/index.md)
- [Pipeline runbook](operations/pipeline-runbook.md)
- [Data sync](operations/data-sync.md)
- [GitHub Actions](operations/github-actions.md)
- [Repair scripts](operations/repair-scripts.md)
- [Quality monitoring](operations/quality-monitoring.md)

### Policies

- [Geo dedup](policies/event-geo-dedup.md)
- [Event renames](policies/event-rename-aliases.md)

## Source of truth

| Topic | Authoritative location |
|-------|------------------------|
| Table / view DDL | `db/migrations/*.sql` |
| Export view → CSV map | `export.py` |
| Normalization maps | `transform/knowledge/`, `transform/normalize.py` |
| Load sequence | `load.py`, `db/sql/promote_core.sql` |
| Committed Tableau files | `data/*.csv` on `main` |

Regenerate schema fragments after migration changes:

```bash
python scripts/generate_schema_docs.py
python scripts/generate_schema_docs.py --live
```

See [Migrations](database/migrations.md).

## Maintaining the docs

1. Edit Markdown under `docs/` in the same PR as code changes.
2. Preview locally: `mkdocs serve` → http://127.0.0.1:8000
3. Push to `main` — GitHub Actions publishes to GitHub Pages automatically.

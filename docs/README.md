# WSDC Data Pipeline — Documentation

English reference for the World Swing Dance Championships data pipeline: parser → Supabase → CSV export → Tableau Public.

## Who should read what

| I am… | Start here |
|-------|------------|
| **Tableau analyst** | [tableau/README.md](tableau/README.md) → [csv-contract.md](tableau/csv-contract.md) → [joins.md](tableau/joins.md) |
| **Developer / maintainer** | [architecture/overview.md](architecture/overview.md) → [database/README.md](database/README.md) → [transform/README.md](transform/README.md) |
| **Ops / on-call** | [operations/README.md](operations/README.md) |

## Documentation map

### Architecture

- [overview.md](architecture/overview.md) — End-to-end pipeline stages and entry points
- [identity-model.md](architecture/identity-model.md) — `event_id`, editions, `geo_event_key`
- [scd2-history.md](architecture/scd2-history.md) — Points and roles change tracking

### Database (Supabase / Postgres)

- [database/README.md](database/README.md) — Schema overview and ER diagrams
- [database/staging.md](database/staging.md) — Parser CSV landing zone
- [database/core.md](database/core.md) — Normalized current state
- [database/history.md](database/history.md) — Run journal and SCD2 tables
- [database/export-views.md](database/export-views.md) — Tableau-facing SQL views
- [database/migrations.md](database/migrations.md) — Migration index and `apply.py`

### Transform & normalization

- [transform/README.md](transform/README.md) — Preprocess pipeline overview
- [transform/divisions-levels.md](transform/divisions-levels.md) — Division / level canonicalization
- [transform/geography.md](transform/geography.md) — Locations, geo_key, metro clusters
- [transform/event-names.md](transform/event-names.md) — Aliases, merges, keep-separate list
- [transform/events-list.md](transform/events-list.md) — Schedule scrape vs points registry

### Tableau

- [tableau/README.md](tableau/README.md) — Weekly refresh workflow
- [tableau/csv-contract.md](tableau/csv-contract.md) — Column catalog for every export CSV
- [tableau/joins.md](tableau/joins.md) — Recommended relationships
- [tableau/dashboards-migration.md](tableau/dashboards-migration.md) — Scheduled events view changes

### Operations

- [operations/README.md](operations/README.md) — Ops index
- [operations/pipeline-runbook.md](operations/pipeline-runbook.md) — Manual runs and failure modes
- [operations/data-sync.md](operations/data-sync.md) — Multi-machine sync rules
- [operations/github-actions.md](operations/github-actions.md) — CI workflows and secrets
- [operations/repair-scripts.md](operations/repair-scripts.md) — One-off DB repair scripts
- [operations/quality-monitoring.md](operations/quality-monitoring.md) — Quality reports and SQL checks

### Policies

- [policies/event-geo-dedup.md](policies/event-geo-dedup.md) — When to merge duplicate `event_id` values
- [policies/event-rename-aliases.md](policies/event-rename-aliases.md) — Schedule rebrand vs points catalog name

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
```

See [database/migrations.md](database/migrations.md).

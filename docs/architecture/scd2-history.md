# SCD2 change history

Points and role summaries are tracked with **Slowly Changing Dimension Type 2** intervals instead of appending full snapshots to ever-growing CSV files.

## Design

| Concept | Implementation |
|---------|----------------|
| Current snapshot | `core.dancer_points`, `core.dancer_roles` (replaced each load) |
| Change log | `history.dancer_points_history`, `history.dancer_roles_history` |
| Run journal | `history.parse_runs` |
| Tableau export | `export.changed_*` views → `changed_dancer_*.csv` |

Each history row is valid during `[valid_from, valid_to]`. **`valid_to IS NULL`** = current open interval for that identity.

## Points history

**Identity:** `(dancer_id, role, dance, level)`

**Tracked attribute:** `total_points`

**Primary key:** `(dancer_id, role, dance, level, valid_from)`

### Weekly load (`record_weekly_points_history.sql`)

Run at start of each `load.py` before `promote_core`:

1. Close open intervals where `total_points` changed vs incoming staging snapshot
2. Insert new open interval for changed identities
3. Attach `run_id` from current `parse_runs` row

### Backfill (`db/sql/backfill_points_history.sql`)

One-time reconstruction from legacy `changed_dancers_points_info.csv` during initial migration. Semantics may differ slightly from weekly SQL — use `scripts/reconcile_points_history.py` to fix drift.

### Reconcile script

```bash
python scripts/reconcile_points_history.py --dry-run
python scripts/reconcile_points_history.py --apply
```

- Closes stale open intervals where points ≠ `core.dancer_points`
- Inserts missing open intervals from core snapshot

Validation (also in `monitor_data_quality.py`):

```sql
SELECT count(*) FROM history.dancer_points_history h
WHERE h.valid_to IS NULL AND NOT EXISTS (
    SELECT 1 FROM core.dancer_points p
    WHERE p.dancer_id = h.dancer_id AND p.role = h.role
      AND p.dance = h.dance AND p.level = h.level
      AND p.total_points = h.total_points
);
-- Target: 0
```

## Roles history

**Identity:** `dancer_id`

**Tracked attributes:** full `dancer_roles` row (dominate/non-dominate fields)

**Primary key:** `(dancer_id, valid_from)`

Weekly: `record_weekly_roles_history.sql`. Backfill: `scripts/backfill_roles_history.py`.

## Export contract

`export.changed_dancer_points_info` and `export.changed_dancer_role_info` mirror old-laptop CSV column order:

- `update_date` in CSV = `valid_from` in history (not `core.dancer_points.update_date`)
- One row per **version** (change), not per weekly snapshot

See [../tableau/csv-contract.md](../tableau/csv-contract.md).

## parse_runs lifecycle

| Column | Meaning |
|--------|---------|
| `run_id` | Surrogate key |
| `source` | `github-actions`, `local`, `backfill` |
| `status` | `running`, `success`, `failed`, `skipped` |
| `started_at` / `finished_at` | Run window |
| `rows_results`, `rows_points` | Load stats |
| `probe_hash`, `max_dancer_id_watermark` | Update checker metadata (migration 006) |

Stuck `running` rows: `scripts/close_parse_runs.py`.

## Future unification

Shared helpers live in `transform/history/scd2.py`. Medium-term goal: weekly SQL and pandas backfill call the same module. Until then, run reconcile after backfill or schema changes.

## Related

- [../database/history.md](../database/history.md) — table field catalogs
- [../operations/repair-scripts.md](../operations/repair-scripts.md) — reconcile command order

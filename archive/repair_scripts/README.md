# Archived one-off DB repair scripts

These scripts fixed a specific data incident. They are **not** part of the
scheduled pipeline. Prefer:

1. A declarative entry under `transform/knowledge/corrections/`
2. A regression test
3. A quality-gate check in `db/quality_checks.py`

Thin wrappers remain under `scripts/` so old docs/commands still resolve, but
they print a deprecation warning and execute the archived file.

| Script | Incident |
|--------|----------|
| `repair_bavarian_allstar_roles_2026.py` | WSDC role swap on Bavarian All-Star 2026 |
| `purge_bavarian_allstar_phantom_points_history.py` | Phantom SCD2 opposite-role points |
| `repair_ndr_highest_from_points.py` | NDR highest-level derived from points |
| `repair_location_poison_aug2026.py` | Shared wrong location_id remap |
| `repair_swingvester_and_schedule_db.py` | SwingVester + empty schedule reload |
| `backfill_roles_history.py` | Legacy roles history backfill |

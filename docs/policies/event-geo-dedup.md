# Event geo dedup policy

Merge WSDC registry `event_id` values only when **normalized name and geography** match.

## Rule

- Same name, **same city/country** (or same metro cluster) → merge candidate (duplicate registry ids).
- Same name, **different city/country** → two geo-events; **do not merge**.
- Metro clusters (e.g. Boston + Framingham, MA) count as one geo for merge purposes.

## Keep separate (hardcoded)

| event_ids | Reason |
|-----------|--------|
| 75, 152 | Worlds UCWDC — Dallas vs Orlando |
| 191, 230 | Sunny Side Dance Camp — Crimea vs Spain |
| 83, 204 | Spring Swing — Detroit vs Stockholm |

## Implementation

| Component | Role |
|-----------|------|
| `transform/geography/geo_event.py` | `geo_key`, `METRO_CLUSTERS`, `classify_event_id_pair` |
| `transform/knowledge/event_aliases.py` | `MERGE_EVENT_ID_MAP` |
| `scripts/merge_event_ids.py` | DB remap with geo gate |
| `scripts/audit_event_splits.py` | Classify split pairs before merge |
| `export.geo_events` | Tableau geo dimension |

## Merge procedure

1. Run `audit_event_splits.py` — confirm `merge_candidate`
2. Add pair to `MERGE_EVENT_ID_MAP` if not already present
3. `merge_event_ids.py --dry-run` — verify row counts and geo
4. Snapshot Supabase branch before production apply
5. `merge_event_ids.py --apply`
6. `export.py` + verify `monitor_data_quality.py`

## Do not

- Merge across different `geo_key` without explicit approval
- Rename `core.events.name` for rebrand-only changes
- Delete merged `event_id` rows — remap `core.results.event_id` only; mark catalog `registry_status = merged`

## Related

- [../architecture/identity-model.md](../architecture/identity-model.md)
- [../transform/geography.md](../transform/geography.md)
- [../operations/repair-scripts.md](../operations/repair-scripts.md)

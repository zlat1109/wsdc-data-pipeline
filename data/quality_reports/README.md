# Data quality reports

After each pipeline run (`load` → `export`), `scripts/data_quality_audit.py` writes:

| File | Purpose |
|------|---------|
| `latest.json` | Most recent audit (compare baseline for **new** findings) |
| `quality_YYYYMMDDTHHMMSSZ.json` | Timestamped history |

## What is logged (not auto-fixed)

- **Event naming**: year suffix in name (`Event 2024`), multiple spellings of same event, names similar to known canonical but unmapped, brand-new event names since last run
- **Locations**: incomplete format, city=country, same `location_id` with different strings
- **Levels**: non-canonical division names
- **Relationships**: orphaned `location_id` / missing catalog entries (from existing validators)

Each finding includes `suggested_fix` pointing to `transform/data_preprocessing.py` maps (same as notebook hardcodes).

## Review workflow

1. Open `latest.json` → filter `"is_new": true`
2. Add rules to `EVENT_NAME_NORMALIZATION`, `EVENT_LOCATION_*`, `LOCATION_INFO_*` in `transform/data_preprocessing.py`
3. Re-run pipeline; new findings should drop on next audit

## Manual run

```bash
python scripts/data_quality_audit.py --data-dir data
```

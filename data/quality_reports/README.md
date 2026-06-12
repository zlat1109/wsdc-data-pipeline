# Data quality reports (combined log)

Written by `scripts/preprocess_data.py` before each load.

## Report structure (`latest.json`)

| Section | Meaning |
|---------|---------|
| **`before_processing`** | Everything found in **raw** CSV before normalization |
| **`applied_normalizations`** | Known rules that ran: notebook maps, auto year-strip on event names, location fixes |
| **`manual_review_required`** | Still open after processing — **needs your decision** |

Each `applied_normalizations.rules[]` entry:

- `rule_id` — e.g. `EVENT_NAME_NORMALIZATION`, `AUTO_STRIP_EVENT_YEAR`
- `from_value` / `to_value` / `rows_affected`
- `source` — `known_map`, `auto_pattern`, `location_id_fix`, …

`manual_review_required.findings[]` with `"is_new": true` — new since last run.

## Workflow

1. Pipeline: parse → **preprocess_data** (normalize + log) → load → export
2. Open `latest.json` → review `manual_review_required` (ignore what `applied_normalizations` already fixed)
3. Add new rules to `transform/data_preprocessing.py` when you decide the fix
4. Next run: before count may stay high, manual_review should shrink

## Manual run

```bash
python scripts/preprocess_data.py --data-dir data
python scripts/preprocess_data.py --data-dir data --dry-run  # log only, no CSV overwrite
```

Legacy: `scripts/data_quality_audit.py` (audit-only, no normalize) — prefer `preprocess_data.py`.

# Quality monitoring

Two layers: preprocess quality reports (CSV) and post-load SQL checks (database).

## Preprocess report

`scripts/preprocess_data.py` writes `data/quality_reports/latest.json`:

| Section | Meaning |
|---------|---------|
| `before_processing` | Raw defects before normalization |
| `applied_normalizations` | Rules applied with row counts |
| `manual_review_required` | Open issues; `"is_new": true` needs decision |

Add fixes to knowledge maps / preprocess based on `manual_review_required`, not items already in `applied_normalizations`.

See [../transform/index.md](../transform/index.md).

### Manual run

```bash
python scripts/preprocess_data.py --data-dir data
python scripts/preprocess_data.py --data-dir data --dry-run
```

Legacy audit-only: `scripts/data_quality_audit.py` (prefer preprocess).

## Post-load SQL checks

`scripts/monitor_data_quality.py` — run after load (also in CI `full-parse.yml`):

| Check | Target | Meaning |
|-------|--------|---------|
| `results_null_location_id` | 0 | All results have location |
| `split_names_same_geo` | 0 | No same-geo duplicate event_ids per raw name |
| `noncanonical_divisions` | 0 | No All-Stars / Champions / Masters |
| `points_history_drift` | 0 | Open history matches core points |

Exit code 1 if any check fails.

```bash
python scripts/monitor_data_quality.py
```

## Event split audit

```bash
python scripts/audit_event_splits.py --output-dir data/quality_reports
```

Output: `event_splits_<timestamp>.json`, `event_splits_latest.json`

Classifications: `merge_candidate`, `keep_separate`, `manual_review`

## CI integration

`full-parse.yml` runs `monitor_data_quality.py` after pipeline when not `export_only`.

Telegram pipeline-complete message includes quality log summary when secrets configured.

## Related

- [repair-scripts.md](repair-scripts.md)
- [../architecture/scd2-history.md](../architecture/scd2-history.md)

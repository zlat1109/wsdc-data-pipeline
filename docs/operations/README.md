# Operations index

Runbooks for pipeline execution, CI, data sync, repairs, and monitoring.

| Doc | When to use |
|-----|-------------|
| [pipeline-runbook.md](pipeline-runbook.md) | Manual parse, load, export |
| [data-sync.md](data-sync.md) | Multi-machine desync, merge datasets |
| [github-actions.md](github-actions.md) | CI secrets, workflows, probe logic |
| [repair-scripts.md](repair-scripts.md) | One-off DB fixes after audit |
| [quality-monitoring.md](quality-monitoring.md) | Quality reports + post-load SQL checks |

## Quick commands

```bash
# Full local pipeline
python scripts/run_pipeline.py --data-dir ./data --source local

# Export only (Supabase → CSV)
python scripts/run_pipeline.py --export-only

# Validate before load
python scripts/validate_pipeline_inputs.py --data-dir ./data

# Post-load checks
python scripts/monitor_data_quality.py
```

## Legacy doc locations

These paths redirect here:

- `docs/MANUAL_PIPELINE.md` → [pipeline-runbook.md](pipeline-runbook.md)
- `docs/DATA_SYNC.md` → [data-sync.md](data-sync.md)
- `docs/GITHUB_ACTIONS.md` → [github-actions.md](github-actions.md)

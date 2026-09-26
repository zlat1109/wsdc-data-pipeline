# Declarative data corrections

Each YAML file is a durable, reviewable fix that preprocess / export / gates
can apply without a one-off DB script.

## Schema

```yaml
id: bavarian-allstar-roles-2026
kind: result_role   # result_role | edition_date | location | event_identity
status: active      # active | expired | superseded
created: 2026-09-20
expires: null       # ISO date or null (= until upstream fixed)
source: "WSDC published inverted roles for Bavarian All-Star 2026"
applies:
  event_id: 233
  event_year: 2026
  event_month: 9
  # kind-specific fields…
notes: "Remove when WSDC republishes corrected roles."
```

## Rules

1. New manual DB repair → add a YAML here + test + quality check first.
2. One-shot `scripts/repair_*.py` only as a temporary bridge; then archive it.
3. `scripts/report_stale_corrections.py` (optional) lists `expires` past today.

Existing Python maps (`result_role_corrections.py`,
`calendar_operator_overrides.py`, `EVENT_NAME_LOCATION_OVERRIDES`) remain the
runtime source of truth until a dedicated loader merges these YAML files.
New corrections should be authored here and mirrored into those modules.

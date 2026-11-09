# Declarative data corrections

Each YAML file is a durable, reviewable fix that preprocess / export / gates
can apply without a one-off DB script.

## Schema

```yaml
id: bavarian-allstar-roles-2026
kind: result_role   # result_role | edition_date | suppress_results | location | event_identity
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

Existing Python helpers (`result_role_corrections.py`,
`calendar_operator_overrides.py`, `EVENT_NAME_LOCATION_OVERRIDES`) still host
imperative logic. Runtime sources of truth for **new** durable fixes:

- `kind: result_role` → loaded by `result_role_rule()` / preprocess Bavarian path
- `kind: edition_date` → `edition_date_repair_fills()` merged in `sync_dump_edition_dates.py`
- `kind: suppress_results` → `drop_suppressed_results()` in preprocess; purge via
  `scripts/purge_suppressed_results.py` (keeps incomplete WSDC editions out until
  republished — e.g. Tampa Bay Classic 2026 places with points=0)

Author corrections here first; keep Python maps only as fallbacks or glue.

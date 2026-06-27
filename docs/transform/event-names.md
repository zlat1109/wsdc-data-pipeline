# Event names and registry merges

Two mechanisms link raw result titles to WSDC registry events: **name aliases** and **id merges**.

## Name aliases (preprocess + load)

### RESULT_TO_CATALOG_EVENT_NAME

Marketing / shortened titles → exact `core.events.name`:

```python
'SwingTime': 'Swingtime in the Rockies'
'UK West Coast Swing Championships': 'UK WCS Championships'
```

### EVENT_NAME_VARIANT_TO_CATALOG

Spelling, casing, year-suffix variants:

```python
'Monterey Swingfest': 'Monterey SwingFest'
'Swing Fling 2024': 'Swing Fling'
```

Year stripping uses `strip_event_year` in `quality_audit.py`, also applied in preprocess.

### build_event_name_normalization()

Merges both dicts for preprocess. Load seeds `core.event_aliases` via `prepare_event_resolution`.

## Registry id merges (same geo only)

`MERGE_EVENT_ID_MAP` in `event_aliases.py` — source_id → canonical_id (all 11 pairs):

| Source | Canonical | Geo / note |
|--------|-----------|------------|
| 66 | 47 | Denver — SwingTime |
| 37 | 195 | Palm Springs New Year |
| 193 | 236 | Warsaw Halloween Swing |
| 99 | 119 | Chicago — Chicagoland |
| 198 | 154 | London — UK WCS |
| 202 | 218 | Singapore — Asia WCS Open |
| 39 | 334 | Boston metro — Countdown Swing |
| 307 | 272 | Paris Westie Fest |
| 325 | 330 | Adelaide — Simply Adelaide |
| 321 | 331 | Brno — Swing Fiction |
| 279 | 283 | Kazan EL Fest |

Applied by `scripts/merge_event_ids.py` (DB mutation, not preprocess).

**Keep separate** (never merge):

| IDs | Reason |
|-----|--------|
| 75, 152 | Worlds UCWDC — Dallas vs Orlando |
| 191, 230 | Sunny Side — Crimea vs Spain |
| 83, 204 | Spring Swing — Detroit vs Stockholm |

## event_name_raw

`core.results.event_name_raw` preserves API title after alias resolution. Export falls back to raw name when `event_id` unresolved.

## Audit tools

```bash
python scripts/audit_event_splits.py --output-dir data/quality_reports
```

Classifies `event_name_raw` values mapping to multiple `event_id` values.

Quality audit codes:

- `EVENT_NAME_VARIANTS_SAME_GEO` — merge candidate
- `EVENT_NAME_VARIANTS_DIFF_GEO` — informational, not duplicate

## Workflow for new alias

1. Add to `RESULT_TO_CATALOG_EVENT_NAME` or `EVENT_NAME_VARIANT_TO_CATALOG`
2. Run preprocess + test in `tests/test_event_name_catalog.py`
3. Load → export
4. Verify `manual_review_required` shrinks in quality report

## Workflow for duplicate registry id

1. Confirm same geo via `audit_event_splits.py`
2. Add to `MERGE_EVENT_ID_MAP` if not keep-separate
3. `merge_event_ids.py --dry-run` then `--apply`
4. Rebuild catalog + export

See [../policies/event-geo-dedup.md](../policies/event-geo-dedup.md).

## Related

- [../policies/event-rename-aliases.md](../policies/event-rename-aliases.md) — schedule vs catalog
- [events-list.md](events-list.md)

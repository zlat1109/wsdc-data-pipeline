# Todd Analytical Datasets — refresh runbook

When Todd ships a new **Analytical Datasets** zip (Competition Results, Event
Editions, Lookup App, Raw Cache), update our DWH and site surfaces in this
order. Do **not** merge Todd folders into the git repo; keep parquet local.

## What’s in the zip

| Folder | Role for us |
|--------|-------------|
| **Competition Results** | `results.parquet` → `core.cr_*` |
| **Event Editions** | `event_editions.parquet` → edition attrs / status / metros / venues / officials |
| **Lookup App** | Local Todd UI only (optional); not ingested |
| **Raw Cache** | Source scrapes for debugging; not ingested |

Default local layout after unzip:

```text
~/Downloads/Analytical Datasets/
  Competition Results/results.parquet
  Event Editions/event_editions.parquet
  Event Editions/export_manifest.json
```

Symlink convenience (optional):

```bash
mkdir -p ~/Downloads/"Competition Results"
ln -sfn ~/Downloads/"Analytical Datasets"/"Competition Results"/results.parquet \
  ~/Downloads/"Competition Results"/results.parquet
```

## 1) Competition Results → `core.cr_*`

Full detail: [competition-results.md](competition-results.md).

```bash
python scripts/load_competition_results.py \
  --cr-path ~/Downloads/"Competition Results"/results.parquet --dry-run

python scripts/load_competition_results.py \
  --cr-path ~/Downloads/"Competition Results"/results.parquet --apply --migrate
```

Acceptance: unmatched editions = 0, offline conflicts OK, report under
`data/quality_reports/cr_load_report.json`.

Then refresh Event Data Registry (Lookup page on analytics site) per the
checklist in competition-results.md (plain local report first; patch Lookup
tbodies only — never `--force-plain-site`).

## 2) Event Editions → enrichment layer

Full detail: [event-editions.md](event-editions.md).

```bash
# Always dry-run first — gate must be green
python scripts/load_event_editions.py \
  --ee-path ~/Downloads/"Analytical Datasets"/"Event Editions"/event_editions.parquet \
  --dry-run --with-metros-venues --with-officials

# Inspect blockers
jq '.gate' data/quality_reports/event_editions_recon.json
```

If the gate blocks:

1. Open `data/quality_reports/event_editions_recon.json` → `gate.issues`
2. Investigate each key (core vs Todd)
3. Add a **case** or **class_rule** to
   [`data/reference/event_editions_decisions.yaml`](../../data/reference/event_editions_decisions.yaml)
4. Re-run dry-run until `gate.ok == true`

```bash
python scripts/load_event_editions.py \
  --ee-path ~/Downloads/"Analytical Datasets"/"Event Editions"/event_editions.parquet \
  --apply --migrate --with-metros-venues --with-officials

python scripts/load_event_editions.py --check-conflicts
```

Then export CSVs for Tableau / site consumers:

```bash
python export.py
```

New files: `edition_attributes.csv`, `edition_status_history.csv`, `metros.csv`,
`venues.csv`, `officials.csv`, `edition_officials.csv`.

### What we never overwrite from Todd

- Occurred edition existence / dates / city → **`core.event_editions`**
- Future schedule → **`core.scheduled_events`**
- Non-WSDC Todd editions → skipped

Todd only fills **new** columns (software, venue, metro, officials, cancelled
history). City/date diffs are acknowledged via class rule
`value_mismatch_core_wins` and logged — core stays SoT.

## 3) After weekly points promote

`promote_core` TRUNCATEs `core.locations` (and related). That **clears**
`locations.metro_id`. CR soft FKs are rematched by CR `--apply`; for metros:

```bash
python scripts/load_event_editions.py \
  --ee-path "$EE_PATH" --apply --with-metros-venues --with-officials
```

(or at least `--with-metros-venues` if officials unchanged).

## 4) Optional local Todd Lookup

```bash
cd ~/Downloads/"Analytical Datasets"/"Lookup App"
python lookup_app.py --results ../"Competition Results"/results.parquet
# http://127.0.0.1:8050/
```

Search CR names as published (e.g. `Mountain Magic Dance Convention`).

## Checklist (each Todd drop)

- [ ] Unzip; confirm `results.parquet` + `event_editions.parquet` + manifests
- [ ] CR dry-run → apply → conflict check
- [ ] Event Data Registry site refresh (Lookup chrome intact)
- [ ] EE dry-run → resolve decisions.yaml if needed → apply with metros/venues/officials
- [ ] EE `--check-conflicts`
- [ ] `python export.py`
- [ ] Spot-check: new weekend edition in `edition_attributes` / Registry / CR

## Related

- [competition-results.md](competition-results.md)
- [event-editions.md](event-editions.md)
- [analytics-site-sync.md](analytics-site-sync.md) (Registry is manual)
- [quality-monitoring.md](quality-monitoring.md)

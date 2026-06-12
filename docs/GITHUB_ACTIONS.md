# GitHub Actions setup

## Required repository secrets

Settings → Secrets and variables → Actions → New repository secret

| Secret | Value |
|---|---|
| `DB_HOST` | `db.<project-ref>.supabase.co` (Direct) or pooler host |
| `DB_PORT` | `5432` |
| `DB_NAME` | `postgres` |
| `DB_USER` | `postgres` (Direct) or `postgres.<project-ref>` (pooler) |
| `DB_PASSWORD` | Database password from Supabase |
| `GOOGLE_MAPS_API_KEY` | For future cloud parser (geocoding) |

Use the **same values** as in your local `.env`.

## Workflows

### `check-updates.yml`

- **Schedule** (Mon–Fri only, ~1×/day, aligned with WSDC publish windows):
  - Mon / Wed / Fri **22:00** Europe/Madrid (CEST → 20:00 UTC)
  - Tue / Thu **09:00** Europe/Madrid (CEST → 07:00 UTC)
  - In CET (winter): same crons = **23:00** and **10:00** Spain time
  - Covers typical California morning/evening drops (~9 h behind Valencia)
- **New-ID scan**: linear probe from last known max dancer ID (watermark)
- New WSDC registry numbers after weekend events → `changed`
- Stores probe result in `history.parse_runs` (`max_dancer_id_watermark`, `new_dancer_ids`)
- If changed → triggers `full-parse.yml`

#### How detection works (matches manual workflow)

1. WSDC assigns new dancer IDs when people first earn points (Newcomer/Novice, etc.)
2. After weekend events, new IDs appear Mon–Fri the following week
3. Script scans IDs `watermark+1, watermark+2, ...` until 5 consecutive misses
4. Any new ID → database updated → trigger parser pipeline

Watermark sources: `MAX(dancer_id)` from `core.dancers` (primary) → last probe record → `PROBE_ANCHOR_ID` env.

### `full-parse.yml`

Manual or auto-triggered pipeline:

1. `db/apply.py` — pending migrations
2. `load.py` — CSV → Supabase (skipped with `export_only=true`)
3. `export.py` — Supabase → `data/*.csv`
4. Git commit + push `data/*.csv`

**Manual run:** Actions → Full WSDC parse pipeline → Run workflow

Options:

- `export_only=true` — refresh Tableau CSV from current Supabase state
- `export_only=false` — requires CSV in `parser_output/` (commit or CI artifact)

## Until cloud parser is enabled

When `check-updates` detects a change:

1. Run parser on your laptop (notebook or script)
2. Copy CSVs to `parser_output/` in the repo
3. Commit and push, or re-run **full-parse** workflow

Cloud notebook parsing (2–3 h, Selenium, IP limits) will be added after a test run.

## Test probe locally

```bash
source .venv/bin/activate
python scripts/check_updates.py --write-probe
```

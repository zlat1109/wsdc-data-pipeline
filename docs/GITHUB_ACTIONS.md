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

- Schedule: every 6 hours (UTC)
- Probes WSDC API for guardian dancer fingerprints
- Stores `probe_hash` in `history.parse_runs`
- If changed → triggers `full-parse.yml`

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
python scripts/check_updates.py --write-hash
```

# GitHub Actions setup

## Required repository secrets

Settings → **Secrets and variables** → **Actions** → **New repository secret**  
Direct link: https://github.com/zlat1109/wsdc-data-pipeline/settings/secrets/actions

### GitHub Actions must use the Supabase **pooler** (IPv4)

Supabase **Direct** host (`db.<ref>.supabase.co`) is **IPv6-only**. GitHub runners have no IPv6 route → `Network is unreachable`.

| Secret | Local `.env` (Direct) | GitHub Secrets (pooler, Session mode) |
|---|---|---|
| `DB_HOST` | `db.tougqwxmahkwnaculiju.supabase.co` | `aws-1-eu-west-2.pooler.supabase.com` |
| `DB_PORT` | `5432` | **`6543`** (Transaction pooler; Session `:5432` may fail) |
| `DB_NAME` | `postgres` | `postgres` |
| `DB_USER` | `postgres` | `postgres.tougqwxmahkwnaculiju` |
| `DB_PASSWORD` | same password | same password |

Copy host/port/user from Supabase Dashboard → **Connect** → **Transaction pooler** (not Direct, not Session if auth fails).

Region prefix is often `aws-1-` (not `aws-0-`) for newer projects.

Optional (not required for probe today):

| Secret | Value |
|---|---|
| `GOOGLE_MAPS_API_KEY` | For future cloud parser (geocoding) |

Password is the same as in Supabase → Project Settings → Database. No quotes in the secret value.

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
- `export_only=false` — loads from `data/` (committed CSVs) by default

## Until cloud parser is enabled

When `check-updates` detects a change:

1. Run parser on your laptop (notebook or script)
2. Copy fresh parser CSVs to `data/` in the repo (or run parser locally first)
3. Commit and push, or re-run **full-parse** workflow

Cloud notebook parsing (2–3 h, Selenium, IP limits) will be added after a test run.

## Test probe locally

```bash
source .venv/bin/activate
python scripts/check_updates.py --write-probe
```

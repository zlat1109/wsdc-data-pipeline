# WSDC Tier chart (Chart 5)

Reference tables for Points Awarded per Tier and competitor-size ranges, sourced from public WSDC rules PDFs and loaded into Supabase (`core.rules_editions`, `core.tier_definitions`, `core.tier_points`).

**Source of truth:** `transform/knowledge/tier_rules.py`  
**Loader:** `python scripts/load_tier_rules.py`  
**PDF text cache:** `data/reference/rules_text/`  
**Reconcile vs results:** `python scripts/reconcile_tier_charts.py`

## Rules editions

<!-- docs-sync:tier-editions -->
| rules_version | valid_from | valid_to | tier_basis | inherits_from | source |
|---|---|---|---|---|---|
| `2002` | 2002-01-01 | 2004-01-03 | `none` | — | pdf_page:WSDC-Points-Registry-2002.pdf#1 |
| `2004` | 2004-01-04 | 2006-12-31 | `none` | 2002 | pdf_page:WSDC-Points-Registry-2004.pdf#1 |
| `2007` | 2007-01-01 | 2008-12-31 | `smaller_role` | — | pdf_page:WSDC Points Registry Document_2007.pdf#1 |
| `2009` | 2009-01-01 | 2010-12-31 | `smaller_role` | — | pdf_page:WSDC Points Registry Document_2009.pdf#1 |
| `2011` | 2011-01-01 | 2015-06-30 | `per_role` | 2009 | pdf_page:WSDC Points Registry Document_2011.pdf#1 |
| `2015` | 2015-07-01 | 2017-12-31 | `per_role` | 2009 | pdf_page:2015-WSDC-Registry-Event-Rules-Combined.pdf#1 |
| `2018` | 2018-01-01 | 2018-12-31 | `per_role` | — | pdf_page:2018-WSDC-Registry-Event-Rules-Combined.pdf#1 |
| `2019` | 2019-01-01 | 2019-12-31 | `per_role` | 2018 | pdf_page:2019-WSDC-Registry-Event-Rules-Combined.pdf#1 |
| `2020` | 2020-01-01 | 2021-04-30 | `per_role` | 2018 | pdf_page:2020-WSDC-Registry-Event-Rules-Combined.pdf#1 |
| `2021-addendum` | 2021-05-01 | 2022-12-31 | `per_role` | 2018 | pdf_page:2020-May-Addendum.pdf#1 |
| `2023.1D` | 2023-01-01 | 2023-12-31 | `per_role` | 2018 | pdf_page:2023-Registry-Event-Rules_vFinal3b-2023.1D.pdf#1 |
| `2024.2B` | 2024-01-01 | 2024-12-31 | `per_role` | 2018 | pdf_page:2024-Registry-Event-Rules_v2024.2B.pdf#1 |
| `2025.1A` | 2025-01-01 | 2025-12-31 | `per_role` | 2018 | pdf_page:wsdcrules.pdf#1 |
| `2026` | 2026-01-01 | — | `per_role` | 2018 | pdf_page:WSDC-Registry-Event-Rules-Jan-17-2026.pdf#17 |
<!-- /docs-sync:tier-editions -->

## Competitor ranges and placement points

Explicit charts (inheritance expanded in the DB loader / `TIER_DEFINITIONS`):

<!-- docs-sync:tier-charts -->
| rules_version | tier | min | max | prelim | finalist_pts | thru | 1st | 2nd | 3rd | 4th | 5th |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `2002` | 0 | 5 | — | 1 | 1 | 10 | 10 | 6 | 4 | 3 | 2 |
| `2007` | 1 | 5 | 15 | 1 | 0 | — | 8 | 6 | 4 | 2 | 1 |
| `2007` | 2 | 16 | 39 | 2 | 1 | 10 | 10 | 8 | 6 | 4 | 2 |
| `2007` | 3 | 40 | — | 3 | 1 | — | 12 | 10 | 8 | 6 | 4 |
| `2009` | 1 | 5 | 15 | 1 | 0 | — | 5 | 4 | 3 | 2 | 1 |
| `2009` | 2 | 16 | 39 | 2 | 1 | 10 | 10 | 8 | 6 | 4 | 2 |
| `2009` | 3 | 40 | — | 3 | 1 | — | 15 | 12 | 10 | 8 | 6 |
| `2018` | 1 | 5 | 10 | 1 | 0 | — | 3 | 2 | 1 | 0 | 0 |
| `2018` | 2 | 11 | 19 | 2 | 0 | — | 6 | 4 | 3 | 2 | 1 |
| `2018` | 3 | 20 | 39 | 2 | 1 | 12 | 10 | 8 | 6 | 4 | 2 |
| `2018` | 4 | 40 | 79 | 3 | 1 | 15 | 15 | 12 | 10 | 8 | 6 |
| `2018` | 5 | 80 | 129 | 3 | 2 | 15 | 20 | 16 | 14 | 12 | 10 |
| `2018` | 6 | 130 | — | 4 | 2 | 15 | 25 | 22 | 18 | 15 | 12 |
<!-- /docs-sync:tier-charts -->

## How to read this

- **tier_basis=`none`** (2002–2006): flat scale, modeled as `tier=0`.
- **`smaller_role`** (2007–2010): Tier from `min(leaders, followers)` couple count; both roles share one inferred Tier.
- **`per_role`** (2011+): Leaders and Followers can have different Tiers in the same division.
- Editions with `inherits_from` reuse the parent Chart 5 numbers (no PDF change to points/ranges).
- **Finalists:** Chart 5 awards points to places 1–5; additional finalists get `finalist_points` (stored as `tier_points.placement=0` / export `points_finalist`). `finalist_max_place` is the deepest place that still gets that award when the PDF specifies a cutoff.

## Empirical check

Observed 1st–5th place point vectors in `dancers_results_info.csv` match these charts by era (`10/6/4/3/2` pre-2007; three-tier charts 2007/2009; six-tier chart from 2018). Run `scripts/reconcile_tier_charts.py` after rule updates.

## Edition inference

After each points load, `db/build_edition_tiers.py` writes `core.edition_division_tiers` (exported as `edition_division_tiers.csv` / `edition_division_entries.csv`):

1. Aggregate points for placements 1–5 per `(edition, division, role, dance)`
2. Exact-match Chart 5 only if ≥3 placements are observed → `matched`
3. Else exact-match another edition’s chart (same completeness rule) → `legacy_chart`
4. Else nearest L1 on the current chart → `matched` with `vector_distance > 0` (sparse zero-distance → `ambiguous`)
5. For `smaller_role` eras, re-align both roles to one shared Tier from the fuller vector
6. Tighten competitor range: `est_min = max(rule_min, scored_dancers)`
7. Pre-2007 flat scale: exact `10/6/4/3/2` → `no_tier_system`; any other distance → `unmatched`

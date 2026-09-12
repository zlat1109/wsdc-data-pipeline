# Entity-relationship diagrams

Current Supabase warehouse as of migrations **001–034**. Source of truth: `db/migrations/*.sql`.

These diagrams show **logical FKs and grains**. Some schedule tables intentionally omit physical FKs to `core.locations` / `core.events` so points-load `TRUNCATE … CASCADE` cannot wipe them (migrations 025, 031).

## Warehouse schemas

```mermaid
flowchart LR
  subgraph staging_s [staging]
    S[Parser CSV text tables]
  end
  subgraph core_s [core]
    C[Normalized current state]
  end
  subgraph history_s [history]
    H[SCD2 + run journals]
  end
  subgraph export_s [export]
    E[Read-only views → CSV]
  end
  S -->|"promote_core.sql"| C
  S -->|"record_*_history.sql"| H
  C --> E
  H --> E
```

| Schema | Mutability | Truncated by points load? |
|--------|------------|---------------------------|
| `staging` | Reload each load | Yes (full replace) |
| `core` (points tables) | Refresh each load | Yes (`TRUNCATE` dancers/results/…) |
| `core` (schedule / calendar / baseline / tiers) | Upsert / rebuild | **No** |
| `history` | Append / close intervals | No |
| `export` | Views only | N/A |

---

## 1. Points & results (core)

Grain of the points pipeline: dancers compete at event editions held at locations.

```mermaid
erDiagram
  levels ||--o{ dancer_points : "level"
  dancers ||--o{ dancer_points : earns
  dancers ||--|| dancer_roles : "role summary"
  dancers ||--o{ dancer_aliases : "aka"
  dancers ||--o{ results : competes
  events ||--o{ results : hosts
  locations ||--o{ results : at
  events ||--o{ event_aliases : "aka"
  events ||--o{ event_instances : "registry rows"

  dancers {
    int dancer_id PK
    text dancer_name
  }
  dancer_aliases {
    text alias PK
    int dancer_id FK
  }
  levels {
    text level PK
    text level_abbr
    int sort_order
  }
  dancer_points {
    int dancer_id PK_FK
    text role PK
    text dance PK
    text level PK_FK
    int total_points
  }
  dancer_roles {
    int dancer_id PK_FK
    text dominate_role
  }
  locations {
    int location_id PK
    text event_city
    text event_country
  }
  events {
    int event_id PK
    text name
  }
  event_aliases {
    text alias PK
    int event_id FK
  }
  event_instances {
    int event_instance_id PK
    int event_id FK
    int location_id FK
  }
  results {
    bigint result_id PK
    int dancer_id FK
    int event_id FK
    int location_id FK
    int event_year
    int event_month
    text event_name_raw
  }
```

**Edition join (logical, not a single FK):**  
`results.(event_id, event_year, event_month)` ↔ `event_editions.(event_id, event_year, event_month)`.

---

## 2. Catalog, editions, calendar, location baseline

Brand-level catalog plus per-edition facts. Calendar dates and location baseline **survive** points `TRUNCATE`.

```mermaid
erDiagram
  events ||--|| event_catalog : summarizes
  events ||--o{ event_editions : has
  locations ||--o{ event_editions : "held_at"
  events ||--o{ edition_calendar_dates : "planned dates"
  events ||--o{ edition_location_baseline : "golden lid"
  locations ||--o{ edition_location_baseline : "baseline place"
  event_editions ||--o{ edition_division_tiers : "inferred tier"
  rules_editions ||--o{ tier_definitions : defines
  rules_editions ||--o{ tier_points : "Chart 5"
  rules_editions ||--o{ edition_division_tiers : "rules_version"

  event_catalog {
    int event_id PK_FK
    text canonical_name
    text typical_location
    text upcoming_location
  }
  event_editions {
    bigint edition_id PK
    int event_id FK
    int event_year UK
    int event_month UK
    int location_id FK
    int result_rows
    text calendar_status
  }
  edition_calendar_dates {
    int event_id PK
    int event_year PK
    int event_month PK
    date planned_start_date
    text calendar_status
    text date_source
  }
  edition_location_baseline {
    int event_id PK_FK
    int event_year PK
    int event_month PK
    int location_id FK
    text source
  }
  edition_division_tiers {
    int event_id PK
    int event_year PK
    int event_month PK
    text division PK
    text role PK
    text dance PK
    int tier
    text status
  }
  rules_editions {
    text rules_version PK
    date valid_from
    date valid_to
  }
  tier_definitions {
    text rules_version PK_FK
    int tier PK
    int min_competitors
    int max_competitors
  }
  tier_points {
    text rules_version PK_FK
    int tier PK
    int placement PK
    int points
  }
```

| Table | Physical FK to `events` / `locations`? | Why it matters |
|-------|----------------------------------------|----------------|
| `event_editions` | Yes | Rebuilt after each load from results + calendar |
| `edition_calendar_dates` | **No** FK to events | Survives `TRUNCATE … CASCADE` on events (025) |
| `edition_location_baseline` | Yes | Drift detection + auto-extend after load (033) |
| `edition_division_tiers` | Logical only | Rebuilt by `build_edition_tiers.py` |

---

## 3. Schedule domain (events list)

Independent of points load. Updated by `scripts/sync_events_list.py` / calendar sync.

```mermaid
erDiagram
  events_list_runs ||--o{ events_list_changes : logs
  events_list_runs ||--o{ scheduled_events : "last_run"
  events_list_runs ||--o{ events_list_current : "last_run"
  events ||--o{ events_list_current : "canonical_event_id"
  locations ||--o{ scheduled_events : "location_id soft"
  locations ||--o{ events_list_current : "location_id soft"

  events_list_runs {
    int run_id PK
    timestamptz started_at
    text status
  }
  events_list_changes {
    int change_id PK
    int run_id FK
    text change_type
  }
  scheduled_events {
    text source_fingerprint PK
    text event_name
    date start_date
    int location_id
    int last_run_id FK
  }
  events_list_current {
    text schedule_event_key PK
    text source_fingerprint
    int canonical_event_id
    int location_id
    text match_status
  }
```

`location_id` on schedule tables is a **soft reference** (no FK) — migration 031.

---

## 4. History / SCD2

```mermaid
erDiagram
  parse_runs ||--o{ dancer_points_history : records
  parse_runs ||--o{ dancer_roles_history : records
  parse_runs ||--o{ dancer_names_history : records
  dancers ||--o{ dancer_points_history : versions
  dancers ||--o{ dancer_roles_history : versions
  dancers ||--o{ dancer_names_history : versions

  parse_runs {
    bigint run_id PK
    text source
    text status
    text probe_hash
  }
  dancer_points_history {
    int dancer_id PK
    text role PK
    text dance PK
    text level PK
    date valid_from PK
    date valid_to
    bigint run_id FK
  }
  dancer_roles_history {
    int dancer_id PK
    date valid_from PK
    date valid_to
    bigint run_id FK
  }
  dancer_names_history {
    int dancer_id PK
    date valid_from PK
    text dancer_name
    date valid_to
    bigint run_id FK
  }
```

Open version = `valid_to IS NULL`. See [SCD2 history](../architecture/scd2-history.md).

---

## 5. Staging → core promote

Staging is all-text and 1:1 with parser CSVs. Promote casts and resolves FKs.

```mermaid
flowchart TB
  subgraph staging [staging]
    sp[dancers_points_info]
    sr[dancer_role_info]
    sres[dancers_results_info]
    sl[location_info]
    se[events_wsdc]
  end
  subgraph core [core]
    dp[dancer_points]
    droles[dancer_roles]
    res[results]
    loc[locations]
    ev[events + event_instances]
    dancers[dancers]
  end
  sp --> dp
  sr --> droles
  sr --> dancers
  sres --> res
  sres --> dancers
  sl --> loc
  se --> ev
```

Changed-dancer staging tables (`staging.changed_*`) feed SCD2 recording, not the full snapshot replace.

---

## 6. Export surface (Tableau)

Default CSVs come from `export.*` views via `export.py`. Full map: [export-views.md](export-views.md).

```mermaid
flowchart LR
  subgraph core_src [core / history]
    C1[results / dancers / locations]
    C2[event_catalog / editions]
    C3[schedule + baseline + tiers]
    H1[SCD2 history]
  end
  subgraph views [export views]
    V1[dancers_* / location_info / events_wsdc]
    V2[event_catalog / event_editions]
    V3[scheduled_events / edition_*]
    V4[changed_dancer_*]
    V5[completed_event_editions]
  end
  C1 --> V1
  C2 --> V2
  C3 --> V3
  H1 --> V4
  C2 --> V5
  C3 --> V5
  V1 --> CSV[data/*.csv]
  V2 --> CSV
  V3 --> CSV
  V4 --> CSV
```

| View | In default `export.py`? | Notes |
|------|-------------------------|-------|
| `export.completed_event_editions` | No | Live VIEW (034); query in Supabase / analytics |
| `export.geo_events` / `results_by_geo_event` | No | Optional analytics |
| `export.scheduled_event_editions` | No | Full schedule archive grain |
| `export.results_by_event` | Opt-in flag | Large |

---

## Related docs

- [Schema overview](index.md)
- [Core tables](core.md)
- [Staging](staging.md)
- [History](history.md)
- [Export views](export-views.md)
- [Event identity](../architecture/identity-model.md)
- [Geography transform](../transform/geography.md) — `location_id` minting / merge-map retirement

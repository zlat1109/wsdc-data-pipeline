# Divisions and levels

Competition divisions (`event_competition` in CSV, `division` in `core.results`) and points levels share the same canonical vocabulary.

## Canonical levels

Defined in `core.levels` (migration 003) and `transform/normalize.py` → `CANONICAL_LEVELS`:

Newcomer, Novice, Intermediate, Advanced, All-Star, Champion, Master, Invitational, Professional, Teacher, Sophisticated, Juniors

Tableau exports use **full words**, not parser abbreviations (`ALS` → `All-Star`).

## LEVEL_ALIASES

`transform/normalize.py` maps parser abbreviations and inconsistent spellings:

| Input examples | Canonical |
|----------------|-----------|
| `ALS`, `ALL`, `All Star`, `All-Stars` | `All-Star` |
| `CHMP`, `Champions` | `Champion` |
| `MSTR`, `Masters` | `Master` |

Functions:

- `normalize_level(value)` — points levels
- `normalize_division(value)` — result divisions (delegates to level normalization)

## Preprocess

`transform/preprocess_with_log.py` applies `normalize_division` to `event_competition` with tracking in quality report.

## Load

`promote_core_results.sql` casts division to text; values should already be canonical from preprocess.

## One-time DB repair

If legacy rows exist in DB:

```bash
python scripts/repair_divisions.py --dry-run
python scripts/repair_divisions.py --apply
```

Targets rows where normalized value differs and is in `CANONICAL_LEVELS`.

## Monitoring

`scripts/monitor_data_quality.py` fails if any rows remain with `division IN ('All-Stars', 'Champions', 'Masters')`.

## Tests

`tests/test_normalize_divisions.py`

## Related

- [../database/core.md](../database/core.md) — `core.results.division`, `core.levels`

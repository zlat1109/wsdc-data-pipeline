# WSDC Data Pipeline

Единый пайплайн данных World Swing Dance Championships (points.worldsdc.com):
парсинг → нормализованная база Supabase (Postgres) → история изменений → CSV-экспорт для Tableau Public.

Заменяет прежнюю схему с ручным запуском парсера на двух ноутбуках и перезаписью CSV.

## Архитектура

```
points.worldsdc.com
        │  (GitHub Actions, cron)
        ▼
   parser/          сбор данных через HTTP API
        ▼
   staging          сырые данные прогона (Supabase)
        ▼
   core             нормализованные сущности: dancers, events,
        │           event_instances, locations, results, dancer_points
        ▼
   history          SCD2: очки, дивизионы, имена + журнал прогонов
        ▼
   export/          SQL-views → CSV (структура 1:1 со старыми файлами)
        ▼
   data/            CSV в git — источник для Tableau Public и других проектов
```

## Структура репозитория

| Путь | Назначение |
|---|---|
| `parser/` | Модули парсера (HTTP API + Selenium fallback) |
| `transform/` | Предобработка и нормализация данных |
| `db/migrations/` | SQL-миграции схем `staging` / `core` / `history` |
| `export/` | Экспорт views в CSV |
| `data/` | Экспортированные CSV (коммитятся автоматически) |
| `tests/` | Юнит-тесты |
| `.github/workflows/` | `check-updates.yml`, `full-parse.yml` |

## Установка

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполнить DATABASE_URL и GOOGLE_MAPS_API_KEY
```

## Использование

```bash
python -m parser.wsdc_parser      # полный парс (локально)
python backfill.py                # первичная загрузка существующих CSV в базу
python load.py                    # staging -> core -> history
python export.py                  # legacy + catalog + history -> data/*.csv
python export.py --include-results-by-event   # + results_by_event.csv (~47 MB)
python export.py --include-results-with-name  # + dancers_results_with_name.csv
```

## Выходные CSV (контракт для Tableau)

### Legacy (без изменений для существующих workbook)

- `dancers_points_info.csv`
- `dancer_role_info.csv`
- `dancers_results_info.csv`
- `location_info.csv`
- `events_wsdc.csv`

Имена и структура колонок сохраняются 1:1 с прежним процессом.

### История изменений (SCD2 → CSV)

Экспортируются автоматически вместе с legacy CSV:

| CSV | Содержимое |
|-----|------------|
| `changed_dancer_points_info.csv` | Изменения очков |
| `changed_dancer_role_info.csv` | Изменения дивизионов (без триггера по имени) |
| `changed_dancer_name_info.csv` | Изменения display name (`history.dancer_names_history`) |

Для имени на **прошлом** result: `python export.py --include-results-with-name` или join `changed_dancer_name_info` в Tableau. См. [docs/tableau/joins.md](docs/tableau/joins.md).

### Каталог ивентов (event-centric dashboards)

Экспортируются автоматически вместе с legacy CSV:

| CSV | View | Назначение |
|-----|------|------------|
| `event_catalog.csv` | `export.event_catalog` | Один ивент = одна строка (name, url, typical location, stats, upcoming) |
| `event_editions.csv` | `export.event_editions` | Ивент × год × месяц (локация edition, число results) |
| `scheduled_events.csv` | `export.scheduled_events` | Актуальное расписание WSDC (registry/trial, одна строка на ивент) |

Опционально (флаг `--include-results-by-event`):

| CSV | View | Назначение |
|-----|------|------------|
| `results_by_event.csv` | `export.results_by_event` | Results + join на catalog и edition (~47 MB) |

**Рекомендуемые join в Tableau Public** (без тяжёлого `results_by_event.csv`):

```
dancers_results_info  ←→  event_editions   ON event_name, event_year, event_month
event_editions        ←→  event_catalog    ON event_id
scheduled_events      ←→  event_catalog    ON canonical_event_id (= event_id)
```

См. [docs/tableau/joins.md](docs/tableau/joins.md). В `dancers_results_info.csv` **нет колонки `event_id`** — только `event_name` + год/месяц.

Rebuild каталога в Supabase после points load (`load.py`) или вручную:

```bash
python scripts/build_event_catalog.py
```

### Tableau Public: еженедельное обновление

Tableau Public не подключается к Supabase — только локальные CSV.

1. GitHub Actions (`full-parse.yml` или `export_only=true`) пишет свежие CSV в `data/` и пушит в репо.
2. Локально: `git pull` в клоне `wsdc-data-pipeline`.
3. В Tableau: **Data → Refresh** (или переоткрыть workbook с путями к `data/*.csv`).

Альтернатива с доступом к БД:

```bash
python export.py --output-dir ./data
```

Расписание WSDC (scrape worldsdc.com/events/ + calendar) обновляется по вторникам — `sync-events-list.yml` коммитит `data/events_list/` и `data/events_calendar/`; day-precision даты пишутся в `core.edition_calendar_dates` и копируются в `event_editions` при rebuild.

## Documentation

**Web site:** [zlat1109.github.io/wsdc-data-pipeline](https://zlat1109.github.io/wsdc-data-pipeline/) (MkDocs Material, auto-deploy on push)

| Audience | Start here |
|----------|------------|
| Tableau analyst | [docs/tableau/index.md](docs/tableau/index.md) |
| Developer / maintainer | [docs/architecture/overview.md](docs/architecture/overview.md) |
| Operations | [docs/operations/index.md](docs/operations/index.md) |

Full index: [docs/index.md](docs/index.md). Local preview: `pip install -r requirements-docs.txt && mkdocs serve`

## Секреты

- Локально — `.env` (в `.gitignore`).
- В CI — GitHub Secrets: см. [docs/operations/github-actions.md](docs/operations/github-actions.md).

## Статус миграции

- [x] Фаза 0: консолидация кода парсера в репозиторий
- [ ] Слияние с эталонной версией со старого ноутбука (отдельный PR)
- [x] Фаза 1: схемы Supabase (`db/migrations/`)
- [x] Фаза 2: `load.py` + `backfill.py`
- [x] Фаза 3: `export.py` + views
- [x] Фаза 4: GitHub Actions (`check-updates.yml`, `full-parse.yml`)
- [x] Фаза 5 (частично): `wsdc-telegram-bot` — автосинк CSV, `scheduled_events.csv`, publication ledger, golden tests для advancement
- [ ] Фаза 5: Tableau Public / analytics repo — переключение на `main` как единственный источник CSV

## Интеграция с wsdc-telegram-bot

После каждого успешного commit CSV в `full-parse.yml`:

1. Pipeline пушит `data/*.csv` + `data/event_aliases.json`
2. `repository_dispatch` → bot `sync-data.yml` (секрет `WSDC_BOT_SYNC_TOKEN`)
3. Bot коммитит свежие CSV в свой `data/` (LFS)

Обратная связь: weekly/results bot пушит weekend snapshots в pipeline (`WSDC_PIPELINE_SYNC_TOKEN` в bot). См. [docs/operations/github-actions.md](docs/operations/github-actions.md).

## Интеграция с wsdc-analytics.github.io

После каждого успешного full-parse export:

1. `scripts/sync_analytics_site.sh` собирает `homepage_kpis.json` и `secondary_country_unified.json` из `data/`
2. Пуш в `wsdc-analytics/wsdc-analytics.github.io` (секрет `WSDC_ANALYTICS_DEPLOY_TOKEN`)

См. [docs/operations/analytics-site-sync.md](docs/operations/analytics-site-sync.md).

Ветка **`old-laptop-version`** — эталонные parser CSV со старого ноутбука для сравнения; не мержить в `main` без `compare_csv_snapshots.py` / `build_merged_load_dataset.py`.

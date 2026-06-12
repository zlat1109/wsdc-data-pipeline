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
   history          SCD2-история изменений очков/уровней + журнал прогонов
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
python export.py                  # core views -> data/*.csv
```

## Выходные CSV (контракт для Tableau)

- `dancers_points_info.csv`
- `dancer_role_info.csv`
- `dancers_results_info.csv`
- `location_info.csv`
- `events_wsdc.csv`

Имена и структура колонок сохраняются 1:1 с прежним процессом — модели данных
в Tableau менять не нужно.

## Секреты

- Локально — `.env` (в `.gitignore`).
- В CI — GitHub Secrets: `DATABASE_URL`, `GOOGLE_MAPS_API_KEY`.

## Статус миграции

- [x] Фаза 0: консолидация кода парсера в репозиторий
- [ ] Слияние с эталонной версией со старого ноутбука (отдельный PR)
- [ ] Фаза 1: схемы Supabase (`db/migrations/`)
- [ ] Фаза 2: `load.py` + `backfill.py`
- [ ] Фаза 3: `export.py` + views
- [ ] Фаза 4: GitHub Actions
- [ ] Фаза 5: переключение потребителей

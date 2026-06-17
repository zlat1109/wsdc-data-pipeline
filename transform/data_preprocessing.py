"""
Скрипт предобработки данных WSDC Points Parser
Применяет нормализацию, валидацию и стандартизацию данных

Использование:
    python data_preprocessing.py
    
Или импорт в ноутбук:
    from data_preprocessing import normalize_geography, normalize_dates, etc.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from dateutil import parser
import re
from typing import Dict, List, Tuple, Optional

from transform.geography import (
    CANADA_PROVINCES,
    CITY_CANONICAL_COORDINATES,
    COUNTRY_STANDARDIZATION,
    STATE_CODE_TO_NAME,
    STATE_NAME_TO_CODE,
    UK_REGIONS,
    canonicalize_city_coordinates,
    fill_international_state,
    fill_us_state_from_location,
    location_city_key,
    normalize_geography,
    parse_us_state_from_location_text,
    standardize_country,
    standardize_location,
    validate_coordinates,
)
from transform.knowledge import (
    EVENT_LOCATION_EXACT_CORRECTIONS,
    EVENT_LOCATION_SUBSTRING_CORRECTIONS,
    EVENT_NAME_LOCATION_OVERRIDES,
    EVENT_NAME_NORMALIZATION,
    LOCATION_INFO_CITY_CORRECTIONS,
    apply_event_corrections,
)
from transform.normalize import normalize_level

# Re-exports for backward compatibility (canonical source: transform.knowledge / transform.geography)

# ═══════════════════════════════════════════════════════════════════
# ФУНКЦИИ НОРМАЛИЗАЦИИ ДАТ
# ═══════════════════════════════════════════════════════════════════

def parse_event_date(date_str: str) -> Optional[pd.Timestamp]:
    """
    Парсит дату из формата "July 1991" или "April 2019"
    
    Args:
        date_str: Строка с датой
        
    Returns:
        pd.Timestamp или None
    """
    if pd.isna(date_str) or date_str == '':
        return None

    text = str(date_str).strip()
    if not text or text.lower() in {"nan", "none"}:
        return None

    # WSDC cloud parse: "Month Year" — always first day of month
    match = re.match(r'(\w+)\s+(\d{4})', text)
    if match:
        month_str, year = match.groups()
        month_map = {
            'January': 1, 'February': 2, 'March': 3, 'April': 4,
            'May': 5, 'June': 6, 'July': 7, 'August': 8,
            'September': 9, 'October': 10, 'November': 11, 'December': 12,
        }
        month = month_map.get(month_str, 1)
        return pd.Timestamp(year=int(year), month=month, day=1)

    if re.match(r'^\d{4}-\d{2}-\d{2}$', text):
        return pd.Timestamp(text)

    try:
        parsed = parser.parse(text)
        return pd.Timestamp(year=parsed.year, month=parsed.month, day=1)
    except (ValueError, TypeError, parser.ParserError):
        return None


def normalize_dates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Нормализует даты в events_wsdc
    
    Args:
        df: DataFrame events_wsdc
        
    Returns:
        Обработанный DataFrame
    """
    df = df.copy()
    
    if 'date' in df.columns:
        # Парсинг дат
        df['parsed_date'] = df['date'].apply(parse_event_date)
        
        # Извлечение компонентов
        df['event_year'] = df['parsed_date'].dt.year
        df['event_month'] = df['parsed_date'].dt.month
        df['event_year_month'] = df['parsed_date'].dt.to_period('M')
    
    return df


def _parse_yam_series(series: pd.Series) -> pd.Series:
    """Parse event_year_and_month values to first-of-month timestamps."""

    def _one(value: object) -> pd.Timestamp:
        if pd.isna(value):
            return pd.NaT
        text = str(value).strip()
        if not text or text.lower() in {"nan", "none"}:
            return pd.NaT
        parsed = parse_event_date(text)
        return parsed if parsed is not None else pd.NaT

    return series.map(_one).astype("datetime64[ns]")


def normalize_results_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize dancers_results_info date columns for promote_core.sql.

    Cloud parse writes event_year_and_month as \"January 1997\" with empty
    event_year/event_month. Load expects numeric year/month and ISO date in
    event_year_and_month (YYYY-MM-DD).
    """
    df = df.copy()
    for col in ("event_year", "event_month", "event_year_and_month"):
        if col not in df.columns:
            df[col] = ""

    year_num = pd.to_numeric(
        df["event_year"].astype(str).str.strip().replace({"": pd.NA, "nan": pd.NA, "None": pd.NA}),
        errors="coerce",
    )
    month_num = pd.to_numeric(
        df["event_month"].astype(str).str.strip().replace({"": pd.NA, "nan": pd.NA, "None": pd.NA}),
        errors="coerce",
    )
    has_ym = year_num.notna() & month_num.notna() & (month_num >= 1) & (month_num <= 12)

    parsed = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    if has_ym.any():
        parsed.loc[has_ym] = pd.to_datetime(
            {
                "year": year_num[has_ym].astype(int),
                "month": month_num[has_ym].astype(int),
                "day": 1,
            },
            errors="coerce",
        )

    missing = parsed.isna()
    if missing.any():
        parsed.loc[missing] = _parse_yam_series(df.loc[missing, "event_year_and_month"])

    df["event_year"] = ""
    df["event_month"] = ""
    df["event_year_and_month"] = ""
    ok = parsed.notna()
    df.loc[ok, "event_year"] = parsed.loc[ok].dt.year.astype(int).astype(str)
    df.loc[ok, "event_month"] = parsed.loc[ok].dt.month.astype(int).astype(str)
    df.loc[ok, "event_year_and_month"] = parsed.loc[ok].dt.strftime("%Y-%m-%d")
    return df


def results_date_parse_rate(df: pd.DataFrame) -> float:
    """Share of rows with parseable event year/month (0.0–1.0)."""
    if df.empty:
        return 1.0
    normalized = normalize_results_dates(df)
    ok = normalized["event_year"].fillna("").astype(str).str.strip() != ""
    return float(ok.mean())


# ═══════════════════════════════════════════════════════════════════
# ФУНКЦИИ СТАНДАРТИЗАЦИИ ФОРМАТОВ
# ═══════════════════════════════════════════════════════════════════

def standardize_result(result: str) -> Optional[str]:
    """
    Стандартизирует формат результата
    
    Args:
        result: Результат в любом формате
        
    Returns:
        Стандартизированный результат
    """
    if pd.isna(result):
        return None
    
    result_str = str(result).strip().upper()
    
    # Числовые результаты
    if result_str.isdigit():
        return int(result_str)
    
    # Специальные результаты
    if result_str in ['F', 'FINAL', 'FINALIST']:
        return 'Final'
    if result_str in ['SF', 'SEMI', 'SEMIFINAL']:
        return 'Semi-Final'
    if result_str in ['QF', 'QUARTER']:
        return 'Quarter-Final'
    
    return result_str


def standardize_formats(data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """
    Применяет стандартизацию форматов ко всем таблицам
    
    Args:
        data: Словарь с DataFrame
        
    Returns:
        Словарь с обработанными DataFrame
    """
    result = {}
    
    # dancer_role_info: нормализация уровней
    if 'dancer_role_info' in data:
        df = data['dancer_role_info'].copy()
        for col in ['dominate_required', 'dominate_allowed', 'non_dominate_required', 'non_dominate_allowed']:
            if col in df.columns:
                df[col] = df[col].apply(normalize_level)
        result['dancer_role_info'] = df
    
    # dancers_results_info: стандартизация результатов
    if 'dancers_results_info' in data:
        df = data['dancers_results_info'].copy()
        if 'event_result' in df.columns:
            df['event_result_standardized'] = df['event_result'].apply(standardize_result)
        # Применяем ручные коррекции по событиям и локациям
        df = apply_event_corrections(df)
        df = normalize_results_dates(df)
        result['dancers_results_info'] = df
    
    # Добавляем остальные таблицы без изменений
    for key, df in data.items():
        if key not in result:
            result[key] = df.copy()
    
    return result


# ═══════════════════════════════════════════════════════════════════
# ФУНКЦИИ ВАЛИДАЦИИ
# ═══════════════════════════════════════════════════════════════════

def validate_location_info(df: pd.DataFrame) -> List[Dict]:
    """Валидация location_info.csv"""
    issues = []
    
    # Проверка обязательных полей
    required_fields = ['location_id', 'event_city', 'event_country']
    for field in required_fields:
        if field in df.columns:
            null_count = df[field].isnull().sum()
            if null_count > 0:
                issues.append({
                    'table': 'location_info',
                    'field': field,
                    'issue': f'{null_count} NULL значений',
                    'severity': 'HIGH'
                })
    
    # Проверка уникальности location_id
    if 'location_id' in df.columns:
        duplicates = df['location_id'].duplicated().sum()
        if duplicates > 0:
            issues.append({
                'table': 'location_info',
                'field': 'location_id',
                'issue': f'{duplicates} дубликатов',
                'severity': 'CRITICAL'
            })
    
    # Проверка координат
    if 'latitude' in df.columns and 'longitude' in df.columns:
        missing_coords = df[
            (df['latitude'].isnull()) | 
            (df['longitude'].isnull())
        ]
        if len(missing_coords) > 0:
            issues.append({
                'table': 'location_info',
                'field': 'coordinates',
                'issue': f'{len(missing_coords)} записей без координат',
                'severity': 'MEDIUM'
            })
    
    return issues


def validate_relationships(data: Dict[str, pd.DataFrame]) -> List[Dict]:
    """Валидация связей между таблицами"""
    issues = []
    
    # Проверка location_id
    if 'dancers_results_info' in data and 'location_info' in data:
        results_location_ids = set(data['dancers_results_info']['location_id'].unique())
        location_info_ids = set(data['location_info']['location_id'].unique())
        
        orphaned_results = results_location_ids - location_info_ids
        if orphaned_results:
            issues.append({
                'table': 'relationships',
                'field': 'location_id',
                'issue': f'{len(orphaned_results)} location_id в results без записи в location_info',
                'severity': 'HIGH',
                'examples': list(orphaned_results)[:10]
            })
    
    # Проверка event_name_id
    if (
        'dancers_results_info' in data
        and 'events_wsdc' in data
        and 'event_name_id' in data['dancers_results_info'].columns
    ):
        results_event_ids = set(data['dancers_results_info']['event_name_id'].unique())
        events_wsdc_ids = set(data['events_wsdc']['id'].unique())
        
        orphaned_events = results_event_ids - events_wsdc_ids
        if orphaned_events:
            issues.append({
                'table': 'relationships',
                'field': 'event_name_id',
                'issue': f'{len(orphaned_events)} event_name_id в results без записи в events_wsdc',
                'severity': 'HIGH',
                'examples': list(orphaned_events)[:10]
            })
    
    # Проверка dancer_id
    if 'dancers_results_info' in data and 'dancer_role_info' in data:
        results_dancer_ids = set(data['dancers_results_info']['dancer_id'].unique())
        role_dancer_ids = set(data['dancer_role_info']['dancer_id'].unique())
        
        orphaned_dancers = results_dancer_ids - role_dancer_ids
        if orphaned_dancers:
            issues.append({
                'table': 'relationships',
                'field': 'dancer_id',
                'issue': f'{len(orphaned_dancers)} dancer_id в results без записи в dancer_role_info',
                'severity': 'MEDIUM',
                'examples': list(orphaned_dancers)[:10]
            })
    
    return issues


def validate_data_quality(data: Dict[str, pd.DataFrame]) -> List[Dict]:
    """
    Комплексная валидация качества данных
    
    Args:
        data: Словарь с DataFrame
        
    Returns:
        Список найденных проблем
    """
    issues = []
    
    # Валидация location_info
    if 'location_info' in data:
        issues.extend(validate_location_info(data['location_info']))
    
    # Валидация связей
    issues.extend(validate_relationships(data))
    
    return issues


# ═══════════════════════════════════════════════════════════════════
# ГЛАВНАЯ ФУНКЦИЯ
# ═══════════════════════════════════════════════════════════════════

def preprocess_all(data: Dict[str, pd.DataFrame]) -> Tuple[Dict[str, pd.DataFrame], List[Dict]]:
    """
    Legacy notebook-style preprocess (no audit log).

    Deprecated: use ``scripts/preprocess_data.py`` / ``preprocess_with_log`` instead.

    Returns:
        Tuple (обработанные данные, список проблем)
    """
    import warnings

    warnings.warn(
        "preprocess_all() is deprecated; use scripts/preprocess_data.py",
        DeprecationWarning,
        stacklevel=2,
    )
    print("🔄 Начало предобработки данных...")
    
    processed_data = {}
    
    # Фаза 1: География
    print("\n📍 Фаза 1: Нормализация географических данных...")
    if 'location_info' in data:
        processed_data['location_info'] = normalize_geography(data['location_info'])
        print(f"   ✅ Обработано {len(processed_data['location_info'])} локаций")
    
    # Фаза 2: Даты
    print("\n📅 Фаза 2: Нормализация дат...")
    if 'events_wsdc' in data:
        processed_data['events_wsdc'] = normalize_dates(data['events_wsdc'])
        print(f"   ✅ Обработано {len(processed_data['events_wsdc'])} событий")
    
    # Фаза 3: Стандартизация
    print("\n📝 Фаза 3: Стандартизация форматов...")
    # Добавляем необработанные таблицы
    for key, df in data.items():
        if key not in processed_data:
            processed_data[key] = df.copy()
    
    processed_data = standardize_formats(processed_data)
    print("   ✅ Форматы стандартизированы")
    
    # Фаза 4: Валидация
    print("\n✅ Фаза 4: Валидация данных...")
    issues = validate_data_quality(processed_data)
    
    if issues:
        print(f"\n⚠️  Найдено {len(issues)} проблем:")
        for issue in issues:
            severity_icon = {'CRITICAL': '🔴', 'HIGH': '🟠', 'MEDIUM': '🟡', 'LOW': '🟢'}.get(issue.get('severity', 'MEDIUM'), '⚪')
            print(f"   {severity_icon} {issue['table']}.{issue['field']}: {issue['issue']}")
            if 'examples' in issue:
                print(f"      Примеры: {issue['examples'][:5]}")
    else:
        print("\n✅ Все проверки пройдены!")
    
    return processed_data, issues


# ═══════════════════════════════════════════════════════════════════
# ЗАГРУЗКА И СОХРАНЕНИЕ
# ═══════════════════════════════════════════════════════════════════

def load_data(data_dir: str = '.') -> Dict[str, pd.DataFrame]:
    """Загружает все CSV файлы"""
    data_path = Path(data_dir)
    data = {}
    
    files = {
        'location_info': 'location_info.csv',
        'events_wsdc': 'events_wsdc.csv',
        'dancers_results_info': 'dancers_results_info.csv',
        'dancer_role_info': 'dancer_role_info.csv',
    }
    
    for key, filename in files.items():
        filepath = data_path / filename
        if filepath.exists():
            print(f"📂 Загрузка {filename}...")
            data[key] = pd.read_csv(filepath, low_memory=False)
            print(f"   ✅ Загружено {len(data[key]):,} записей")
        else:
            print(f"   ⚠️  Файл {filename} не найден")
    
    return data


def save_processed_data(data: Dict[str, pd.DataFrame], output_dir: str = 'processed') -> None:
    """Сохраняет обработанные данные"""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    for name, df in data.items():
        output_file = output_path / f"{name}_processed.csv"
        df.to_csv(output_file, index=False)
        print(f"💾 Сохранено: {output_file}")


if __name__ == '__main__':
    # Загрузка
    print("=" * 80)
    print("🔄 ПРЕДОБРАБОТКА ДАННЫХ WSDC POINTS PARSER")
    print("=" * 80)
    
    data = load_data()
    
    if not data:
        print("\n❌ Нет данных для обработки!")
        exit(1)
    
    # Предобработка
    processed_data, issues = preprocess_all(data)
    
    # Сохранение
    print("\n💾 Сохранение обработанных данных...")
    save_processed_data(processed_data)
    
    print("\n🎉 Предобработка завершена!")
    print(f"   📊 Обработано таблиц: {len(processed_data)}")
    print(f"   ⚠️  Найдено проблем: {len(issues)}")

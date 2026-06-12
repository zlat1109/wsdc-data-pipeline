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

# ═══════════════════════════════════════════════════════════════════
# КОНСТАНТЫ И MAPPINGS
# ═══════════════════════════════════════════════════════════════════

# Стандартизация стран
COUNTRY_STANDARDIZATION = {
    'US': 'United States',
    'USA': 'United States',
    'Usa': 'United States',
    'United States': 'United States',
    'UK': 'United Kingdom',
    'United Kingdom': 'United Kingdom',
    'CAN': 'Canada',
    'Canada': 'Canada',
    'AUS': 'Australia',
    'Australia': 'Australia',
    'DEU': 'Germany',
    'Germany': 'Germany',
    'FRA': 'France',
    'France': 'France',
    'ITA': 'Italy',
    'Italy': 'Italy',
    'RUS': 'Russia',
    'Russia': 'Russia',
    'ESP': 'Spain',
    'Spain': 'Spain',
    'NLD': 'Netherlands',
    'Netherlands': 'Netherlands',
    'POL': 'Poland',
    'Poland': 'Poland',
    'Polska': 'Poland',
    'SWE': 'Sweden',
    'Sweden': 'Sweden',
    'NOR': 'Norway',
    'Norway': 'Norway',
    'DNK': 'Denmark',
    'Denmark': 'Denmark',
    'FIN': 'Finland',
    'Finland': 'Finland',
    'Finalnd': 'Finland',
    'BEL': 'Belgium',
    'Belgium': 'Belgium',
    'Belgique': 'Belgium',
    'CHE': 'Switzerland',
    'Switzerland': 'Switzerland',
    'AUT': 'Austria',
    'Austria': 'Austria',
    'ISR': 'Israel',
    'Israel': 'Israel',
    'HUN': 'Hungary',
    'Hungary': 'Hungary',
    'UKR': 'Ukraine',
    'Ukraine': 'Ukraine',
    'CZE': 'Czech Republic',
    'Czech Republic': 'Czech Republic',
    'PRT': 'Portugal',
    'Portugal': 'Portugal',
    'GRC': 'Greece',
    'Greece': 'Greece',
    'IRL': 'Ireland',
    'Ireland': 'Ireland',
    'SGP': 'Singapore',
    'Singapore': 'Singapore',
    # Ошибочно используемое название города как страны
    'Albany': 'United States',
}

# Преобразование названий штатов в коды (US)
STATE_NAME_TO_CODE = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR',
    'California': 'CA', 'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE',
    'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID',
    'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS',
    'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
    'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS',
    'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
    'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY',
    'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK',
    'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
    'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT',
    'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV',
    'Wisconsin': 'WI', 'Wyoming': 'WY', 'District of Columbia': 'DC',
}

# Провинции Канады
CANADA_PROVINCES = {
    'Toronto': 'Ontario',
    'Montreal': 'Quebec',
    'Vancouver': 'British Columbia',
    'Calgary': 'Alberta',
    'Edmonton': 'Alberta',
    'Ottawa': 'Ontario',
    'Winnipeg': 'Manitoba',
    'Quebec City': 'Quebec',
    'Hamilton': 'Ontario',
    'Kitchener': 'Ontario',
    'London': 'Ontario',
    'Victoria': 'British Columbia',
    'Halifax': 'Nova Scotia',
    'Oshawa': 'Ontario',
    'Windsor': 'Ontario',
    'Saskatoon': 'Saskatchewan',
    'Regina': 'Saskatchewan',
    'Sherbrooke': 'Quebec',
    'St. John\'s': 'Newfoundland and Labrador',
    'Barrie': 'Ontario',
    'Richmond': 'British Columbia',
}

# Регионы Великобритании
UK_REGIONS = {
    'London': 'England',
    'Manchester': 'England',
    'Birmingham': 'England',
    'Liverpool': 'England',
    'Leeds': 'England',
    'Sheffield': 'England',
    'Edinburgh': 'Scotland',
    'Glasgow': 'Scotland',
    'Bristol': 'England',
    'Cardiff': 'Wales',
    'Belfast': 'Northern Ireland',
    'Newcastle': 'England',
    'Nottingham': 'England',
    'Leicester': 'England',
    'Coventry': 'England',
    'Sipson': 'England',
}

# Ручные коррекции названий и локаций событий,
# ранее задавались хардкодом в ноутбуке

# Нормализация названий событий
EVENT_NAME_NORMALIZATION = {
    'Scandinavian Open WCS': 'Scandinavian Open',
    'Scandinavian Open WCS 2022': 'Scandinavian Open',
    'Scandinavian Open WCS "SNOW"': 'Scandinavian Open',
    # Выявленные неочевидные варианты написания
    'Americano Dance camp': 'Americano Dance Camp',
    'Rock The Barn': 'Rock the Barn',
    'Go West Swingfest': 'Go West SwingFest',
    'D-TOWNSWING': 'D-Townswing',
    'KING SWING': 'King Swing',
    'SWINGAPALOOZA': 'Swingapalooza',
    'London SWINGvitational': 'London SwingVitational',
    'Westies on The Water': 'Westies on the Water',
    'Boogie by the Bay': 'Boogie By The Bay',
    'Swingvester': 'SwingVester',
    'West In Lyon': 'West in Lyon',
    'Paradise dance festival': 'Paradise Dance Festival',
    'WESTY NANTES': 'Westy Nantes',
    'BALTIC SWING': 'Baltic Swing',
    'Halloween Swingthing': 'Halloween SwingThing',
}

# Переопределение локаций по названию события
EVENT_NAME_LOCATION_OVERRIDES = {
    'Go West Swing Fest': 'Fremantle, Australia',
    'Scandinavian Open': 'Stockholm, Sweden',
    'BeeMAD': 'Madrid, Spain',
}

# Точные замены значений event_location
EVENT_LOCATION_EXACT_CORRECTIONS = {
    'Adelaide, South Australia, Australia': 'Adelaide, Australia',
    'Budapest': 'Budapest, Hungary',
    'Calgar Yy, Alberta': 'Calgary, Canada',
    'Czech Republic': 'Brno, Czech Republic',
    'Dallas, Texas': 'Dallas, TX',
    'East Rutherford': 'East Rutherford, NJ',
    'Edmonton, ON': 'Edmonton, Canada',
    'Gold Coast, Queensland': 'Gold Coast, Australia',
    'Israel': 'Tel Aviv, Israel',
    'Ottawa': 'Ottawa, Canada',
    'Paris': 'Paris, France',
    'Sweden': 'Stockholm, Sweden',
    'Toulouse': 'Toulouse, France',
    'Redmond, Oregon': 'Redmond, OR',
    'Seoul, South Korea': 'Seoul, Republic of Korea',
    'Seoul, Korea': 'Seoul, Republic of Korea',
    'Concord CA': 'Concord, CA',
    'St. Burlatskaya, Russia': 'Samara, Russia',
    # Выявленные дубликаты и неконсистентные варианты
    'CHICAGO, IL, United States': 'Chicago, IL, United States',
    'St. Louis, Mo, USA': 'St. Louis, MO, USA',
    'PARIS, France': 'Paris, France',
    'Moscow,  Russia': 'Moscow, Russia',
    'Stockholm,  Sweden': 'Stockholm, Sweden',
    'Singapore': 'Singapore, Singapore',
    # Город без штата/страны — приводим к формату City, State Code
    'New York': 'New York, NY',
}

# Подстрочные замены в event_location
EVENT_LOCATION_SUBSTRING_CORRECTIONS = [
    ('Scotland', 'United Kingdom'),
    ('ENGLAND', 'United Kingdom'),
    ('England', 'United Kingdom'),
    ('UK', 'United Kingdom'),
    ('FRANCE', 'France'),
    ('QC Canada', 'Canada'),
    ('QC', 'Canada'),
    ('Isreal', 'Israel'),
    ('Washington Dc', 'Washington'),
    ('Kindom', 'Kingdom'),
    ('Italia', 'Italy'),
    ('BC', 'Canada'),
    ('Bernadino', 'Bernardino'),
    ('Minn / St. Paul', 'St. Paul'),
]

# Коррекции для конкретных location_id в location_info
# (когда исходные данные полностью пустые, но по бизнес-знанию
#  мы знаем город и страну)
LOCATION_INFO_ID_CORRECTIONS = {
    # Scandinavian Open — проходит в Stockholm, Sweden
    222: {
        'event_city': 'Stockholm',
        'event_state': '',
        'event_country': 'Sweden',
        'event_location': 'Stockholm, Sweden',
        'event_location_standardized': 'Stockholm, Sweden',
    },
    # Albany, NY, USA — явно США, но в country было Albany и отсутствует штат
    158: {
        'event_city': 'Albany',
        'event_state': 'New York',
        'event_country': 'United States',
        'event_location': 'Albany, NY',
        'event_location_standardized': 'Albany, NY',
    },
}

# Коррекции по городу в location_info (ключ — event_city в нижнем регистре;
# применяются когда по городу неправильно определились штат/страна)
# event_state храним полным названием штата (как в остальных записях)
LOCATION_INFO_CITY_CORRECTIONS = {
    'new york': {
        'event_city': 'New York',
        'event_state': 'New York',
        'event_country': 'United States',
        'event_location': 'New York, NY',
        'event_location_standardized': 'New York, NY',
    },
    'san antonio': {
        'event_city': 'San Antonio',
        'event_state': 'Texas',
        'event_country': 'United States',
        'event_location': 'San Antonio, TX',
        'event_location_standardized': 'San Antonio, TX',
    },
}

# Нормализация уровней дивизионов
LEVEL_NORMALIZATION = {
    # Short format → Full format
    'NEW': 'Newcomer',
    'NOV': 'Novice',
    'INT': 'Intermediate',
    'ADV': 'Advanced',
    'ALS': 'All Star',
    'CHMP': 'Champion',
    # Full format → Full format (для консистентности)
    'Newcomer': 'Newcomer',
    'Novice': 'Novice',
    'Intermediate': 'Intermediate',
    'Advanced': 'Advanced',
    'All Star': 'All Star',
    'Champion': 'Champion',
    # Варианты написания
    'All-Star': 'All Star',
    'Allstar': 'All Star',
    'Champions': 'Champion',
}

# ═══════════════════════════════════════════════════════════════════
# ФУНКЦИИ НОРМАЛИЗАЦИИ ГЕОГРАФИИ
# ═══════════════════════════════════════════════════════════════════

def standardize_country(country: str) -> Optional[str]:
    """
    Стандартизирует название страны
    
    Args:
        country: Название страны (может быть в разных форматах)
        
    Returns:
        Стандартизированное название страны или None
    """
    if pd.isna(country) or country == '':
        return None
    
    country_str = str(country).strip()
    return COUNTRY_STANDARDIZATION.get(country_str, country_str)


def standardize_location(row: pd.Series) -> str:
    """
    Стандартизирует формат location:
    - US: "City, State Code"
    - Другие: "City, Country"
    
    Args:
        row: Строка DataFrame с полями event_city, event_state, event_country
        
    Returns:
        Стандартизированная строка локации
    """
    city = str(row.get('event_city', '')).strip()
    state = str(row.get('event_state', '')).strip() if pd.notna(row.get('event_state')) else ''
    country = str(row.get('event_country', '')).strip() if pd.notna(row.get('event_country')) else ''
    
    if country == 'United States' and state:
        # US формат: "City, State Code"
        state_code = STATE_NAME_TO_CODE.get(state, state)
        return f"{city}, {state_code}"
    elif country:
        # Международный формат: "City, Country"
        return f"{city}, {country}"
    else:
        return city


def fill_international_state(row: pd.Series) -> str:
    """
    Заполняет event_state для не-US локаций
    
    Args:
        row: Строка DataFrame
        
    Returns:
        Заполненное значение event_state
    """
    if pd.notna(row.get('event_state')) and str(row.get('event_state')).strip():
        return str(row.get('event_state')).strip()
    
    country = str(row.get('event_country', '')).strip() if pd.notna(row.get('event_country')) else ''
    city = str(row.get('event_city', '')).strip() if pd.notna(row.get('event_city')) else ''
    
    if country == 'Canada':
        return CANADA_PROVINCES.get(city, '')
    elif country == 'United Kingdom':
        return UK_REGIONS.get(city, '')
    
    return ''


def validate_coordinates(row: pd.Series) -> bool:
    """
    Валидирует координаты
    
    Args:
        row: Строка DataFrame с полями latitude, longitude
        
    Returns:
        True если координаты валидны, False иначе
    """
    lat = row.get('latitude')
    lon = row.get('longitude')
    
    if pd.isna(lat) or pd.isna(lon):
        return False
    
    try:
        lat_float = float(lat)
        lon_float = float(lon)
        
        # Проверка диапазонов
        if not (-90 <= lat_float <= 90):
            return False
        if not (-180 <= lon_float <= 180):
            return False
        
        return True
    except (ValueError, TypeError):
        return False


def normalize_geography(df: pd.DataFrame) -> pd.DataFrame:
    """
    Применяет все нормализации географических данных
    
    Args:
        df: DataFrame location_info
        
    Returns:
        Обработанный DataFrame
    """
    df = df.copy()

    # 0. Специальные коррекции для конкретных location_id (если колонка есть)
    if 'location_id' in df.columns:
        for loc_id, fixes in LOCATION_INFO_ID_CORRECTIONS.items():
            # Базовая маска по ID
            mask = df['location_id'] == loc_id
            if not mask.any():
                continue

            # Дополнительная защита: меняем только «пустые» записи,
            # чтобы при смене генерации ID не перезатереть валидные данные.
            empty_mask = mask
            # Если в фиксе указаны ключевые поля (city/country/location),
            # считаем запись «пустой», если они NaN/пустые.
            for key_col in ['event_city', 'event_country', 'event_location']:
                if key_col in df.columns and key_col in fixes:
                    col_vals = df.loc[mask, key_col].astype(str).str.strip()
                    empty_mask &= col_vals.isna() | (col_vals == '') | (col_vals == 'nan')

            target_mask = empty_mask if empty_mask.any() else mask

            for col, val in fixes.items():
                if col in df.columns:
                    df.loc[target_mask, col] = val

    # 0b. Коррекции по городу (не зависят от location_id)
    if 'event_city' in df.columns:
        city_col = df['event_city'].fillna('').astype(str).str.strip()
        for city_key, fixes in LOCATION_INFO_CITY_CORRECTIONS.items():
            mask = city_col.str.lower() == city_key
            if mask.any():
                for col, val in fixes.items():
                    if col in df.columns:
                        df.loc[mask, col] = val
    
    # 1. Стандартизация стран
    if 'event_country' in df.columns:
        df['event_country'] = df['event_country'].apply(standardize_country)
    
    # 2. Заполнение event_state для международных локаций
    if 'event_state' in df.columns:
        df['event_state'] = df.apply(fill_international_state, axis=1)
    
    # 3. Стандартизация локаций
    if 'event_location' in df.columns:
        df['event_location_standardized'] = df.apply(standardize_location, axis=1)
    
    # 4. Валидация координат
    if 'latitude' in df.columns and 'longitude' in df.columns:
        df['coordinates_valid'] = df.apply(validate_coordinates, axis=1)
    
    return df


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
    
    try:
        # Попытка прямого парсинга
        return parser.parse(str(date_str))
    except:
        # Обработка формата "Month Year"
        match = re.match(r'(\w+)\s+(\d{4})', str(date_str))
        if match:
            month_str, year = match.groups()
            # Преобразуем месяц в число
            month_map = {
                'January': 1, 'February': 2, 'March': 3, 'April': 4,
                'May': 5, 'June': 6, 'July': 7, 'August': 8,
                'September': 9, 'October': 10, 'November': 11, 'December': 12
            }
            month = month_map.get(month_str, 1)
            return pd.Timestamp(year=int(year), month=month, day=1)
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


# ═══════════════════════════════════════════════════════════════════
# ФУНКЦИИ СТАНДАРТИЗАЦИИ ФОРМАТОВ
# ═══════════════════════════════════════════════════════════════════

def normalize_level(level: str) -> Optional[str]:
    """
    Нормализует уровень дивизиона
    
    Args:
        level: Уровень в любом формате
        
    Returns:
        Нормализованный уровень или None
    """
    if pd.isna(level) or level == '' or str(level).strip() == '':
        return None
    
    level_str = str(level).strip().upper()
    
    # Попытка найти в mapping
    for key, value in LEVEL_NORMALIZATION.items():
        if key.upper() == level_str:
            return value
    
    # Fallback: capitalize
    return str(level).strip().title()


def apply_event_corrections(df: pd.DataFrame) -> pd.DataFrame:
    """
    Применяет ручные коррекции к названиям и локациям событий
    (то, что ранее задавалось хардкодом в ноутбуке).
    """
    df = df.copy()

    # 1. Коррекция названий событий
    if 'event_name' in df.columns:
        df['event_name'] = df['event_name'].replace(EVENT_NAME_NORMALIZATION)

        # Переопределение локаций по названию события
        if 'event_location' in df.columns:
            for name, location in EVENT_NAME_LOCATION_OVERRIDES.items():
                mask = df['event_name'] == name
                if mask.any():
                    df.loc[mask, 'event_location'] = location

    # 2. Коррекция локаций
    if 'event_location' in df.columns:
        # Точные замены
        df['event_location'] = df['event_location'].replace(EVENT_LOCATION_EXACT_CORRECTIONS)

        # Подстрочные замены
        for old, new in EVENT_LOCATION_SUBSTRING_CORRECTIONS:
            df['event_location'] = df['event_location'].str.replace(old, new, regex=False)

    return df


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
    if 'dancers_results_info' in data and 'events_wsdc' in data:
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
    Применяет все этапы предобработки
    
    Args:
        data: Словарь с DataFrame
        
    Returns:
        Tuple (обработанные данные, список проблем)
    """
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

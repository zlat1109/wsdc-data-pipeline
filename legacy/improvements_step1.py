# ============================================================================
# ЭТАП 1: КОНФИГУРАЦИЯ И ЛОГИРОВАНИЕ
# Скопируйте этот код в новую ячейку в начале вашего notebook'а
# ============================================================================

import pandas as pd
import numpy as np
from datetime import datetime
import re
import json
import traceback
import urllib3
import requests
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import googlemaps
from geopy.geocoders import Nominatim
import warnings
import logging
import os
from typing import Dict, List, Optional, Any, Union

# Игнорирование предупреждений
warnings.filterwarnings('ignore')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# ============================================================================

def setup_logging():
    """Настройка логирования для отладки"""
    # Создаем папку для логов, если её нет
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/wsdc_parser.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Логирование настроено")
    return logger

# Инициализация логгера
logger = setup_logging()

# ============================================================================
# ФУНКЦИИ ДЛЯ ОПРЕДЕЛЕНИЯ НАЧАЛЬНОГО ID
# ============================================================================

def get_max_dancer_id_from_csv(filename='dancer_role_info.csv'):
    """
    Получение максимального ID танцора из CSV файла
    
    Args:
        filename (str): Путь к CSV файлу
        
    Returns:
        int: Максимальный ID танцора или 26410 по умолчанию
    """
    try:
        if not os.path.exists(filename):
            logger.warning(f"Файл {filename} не найден, используем ID по умолчанию")
            return 26410
        
        df = pd.read_csv(filename)
        if 'dancer_id' in df.columns and not df['dancer_id'].empty:
            max_id = df['dancer_id'].max()
            logger.info(f"Найден максимальный ID танцора в {filename}: {max_id}")
            return int(max_id)
        else:
            logger.warning(f"Колонка 'dancer_id' не найдена в {filename}, используем ID по умолчанию")
            return 26410
            
    except Exception as e:
        logger.error(f"Ошибка при чтении {filename}: {e}")
        return 26410

def get_max_dancer_id_from_all_sources():
    """
    Получение максимального ID танцора из всех доступных источников
    
    Returns:
        int: Максимальный ID танцора
    """
    csv_files = [
        'dancer_role_info.csv',
        'dancers_points_info.csv', 
        'dancers_results_info.csv'
    ]
    
    max_ids = []
    
    for filename in csv_files:
        try:
            if os.path.exists(filename):
                df = pd.read_csv(filename)
                if 'dancer_id' in df.columns and not df['dancer_id'].empty:
                    max_id = df['dancer_id'].max()
                    max_ids.append(max_id)
                    logger.info(f"Максимальный ID в {filename}: {max_id}")
        except Exception as e:
            logger.warning(f"Ошибка при чтении {filename}: {e}")
    
    if max_ids:
        overall_max = max(max_ids)
        logger.info(f"Общий максимальный ID из всех источников: {overall_max}")
        return int(overall_max)
    else:
        logger.warning("Не удалось найти данные, используем ID по умолчанию")
        return 26410

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

class Config:
    """Конфигурация для WSDC Points Parser"""
    
    # URLs
    CHECK_CONTESTERS_URL = 'https://points.worldsdc.com/lookup/autocomplete?q='
    TOKEN_URL = 'https://points.worldsdc.com/lookup2020'
    LOOKUP_URL = 'https://points.worldsdc.com/lookup2020'
    
    # Настройки безопасности
    VERIFY_SSL = True
    TIMEOUT = 10
    MAX_RETRIES = 3
    
    # Настройки парсинга
    MAX_ATTEMPTS = 5
    
    # Автоматическое определение начального ID
    @classmethod
    def get_start_dancer_id(cls):
        """Получение начального ID танцора из данных"""
        return get_max_dancer_id_from_all_sources()
    
    # Заголовки для запросов
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    # Специфичные заголовки для разных типов запросов
    CHECK_CONTESTERS_HEADERS = {
        **HEADERS,
        'Referer': 'https://points.worldsdc.com/lookup2020',
        'X-Requested-With': 'XMLHttpRequest',
    }
    
    TOKEN_HEADERS = {
        **HEADERS,
        'Referer': 'https://points.worldsdc.com/lookup2020',
    }
    
    CONTESTER_HEADERS = {
        **HEADERS,
        'Referer': 'https://points.worldsdc.com/lookup',
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'Origin': 'https://points.worldsdc.com/lookup2020',
        'X-Requested-With': 'XMLHttpRequest',
    }
    
    # Настройки Chrome
    CHROME_OPTIONS = [
        '--disable-gpu',
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-blink-features=AutomationControlled',
        '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]

# Инициализация конфигурации
config = Config()
logger.info("Конфигурация загружена")

# ============================================================================
# КЛАССЫ ИСКЛЮЧЕНИЙ
# ============================================================================

class TokenNotFoundError(Exception):
    """Исключение для случая, когда токен не найден"""
    pass

class DancerNotFoundError(Exception):
    """Исключение для случая, когда танцор не найден"""
    pass

class NetworkError(Exception):
    """Исключение для сетевых ошибок"""
    pass

class ValidationError(Exception):
    """Исключение для ошибок валидации данных"""
    pass

logger.info("Классы исключений определены")

# ============================================================================
# ИНФОРМАЦИЯ О НАЧАЛЬНОМ ID
# ============================================================================

# Получаем начальный ID из данных
start_dancer_id = config.get_start_dancer_id()

print("✅ Конфигурация и логирование настроены!")
print(f"📁 Логи сохраняются в: logs/wsdc_parser.log")
print(f"🔧 Начальный ID танцора (из данных): {start_dancer_id}")
print(f"⏱️ Таймаут запросов: {config.TIMEOUT} сек")
print(f"🔄 Максимум попыток: {config.MAX_RETRIES}")

# Дополнительная информация о данных
try:
    if os.path.exists('dancer_role_info.csv'):
        df = pd.read_csv('dancer_role_info.csv')
        print(f"📊 Загружено записей: {len(df)}")
        print(f"📈 Диапазон ID: {df['dancer_id'].min()} - {df['dancer_id'].max()}")
except Exception as e:
    print(f"⚠️ Не удалось прочитать данные: {e}")

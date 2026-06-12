import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Конфигурация для WSDC Points Parser"""
    
    # URLs
    CHECK_CONTESTERS_URL = os.getenv('CHECK_CONTESTERS_URL', 'https://points.worldsdc.com/lookup/autocomplete?q=')
    TOKEN_URL = os.getenv('TOKEN_URL', 'https://points.worldsdc.com/lookup2020')
    LOOKUP_URL = os.getenv('LOOKUP_URL', 'https://points.worldsdc.com/lookup2020/find')
    
    # Настройки безопасности
    VERIFY_SSL = os.getenv('VERIFY_SSL', 'true').lower() == 'true'
    TIMEOUT = int(os.getenv('TIMEOUT', '10'))
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
    
    # Настройки парсинга
    MAX_ATTEMPTS = int(os.getenv('MAX_ATTEMPTS', '5'))
    START_DANCER_ID = int(os.getenv('START_DANCER_ID', '26410'))
    
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


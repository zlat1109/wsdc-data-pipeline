import logging
import os
from datetime import datetime

def setup_logger(name='wsdc_parser', log_level='INFO'):
    """
    Настройка логгера для WSDC Parser
    
    Args:
        name (str): Имя логгера
        log_level (str): Уровень логирования
    
    Returns:
        logging.Logger: Настроенный логгер
    """
    
    # Создаем директорию для логов если её нет
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Настройка формата логов
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Создаем логгер
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Очищаем существующие хендлеры
    logger.handlers.clear()
    
    # Хендлер для файла
    log_filename = f'{log_dir}/wsdc_parser_{datetime.now().strftime("%Y%m%d")}.log'
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # Хендлер для консоли
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Форматтеры
    file_formatter = logging.Formatter(log_format, date_format)
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    
    file_handler.setFormatter(file_formatter)
    console_handler.setFormatter(console_formatter)
    
    # Добавляем хендлеры к логгеру
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Создаем основной логгер
logger = setup_logger()


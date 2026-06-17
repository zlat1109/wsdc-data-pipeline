"""
Data Processors Module
Улучшенные функции для обработки данных WSDC
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import re
from .logger import logger
from .exceptions import ValidationError


class DataCleaner:
    """Класс для очистки и валидации данных"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """
        Очистка текста от лишних символов
        
        Args:
            text (str): Исходный текст
            
        Returns:
            str: Очищенный текст
        """
        if not isinstance(text, str):
            return ""
        
        # Удаляем табуляцию и лишние пробелы
        cleaned = text.replace('\t', '').strip()
        # Удаляем множественные пробелы
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned
    
    @staticmethod
    def validate_dancer_id(dancer_id: Any) -> bool:
        """
        Валидация ID танцора
        
        Args:
            dancer_id: ID для проверки
            
        Returns:
            bool: True если ID валидный
        """
        try:
            dancer_id = int(dancer_id)
            return dancer_id > 0
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_location(location: str) -> bool:
        """
        Валидация локации
        
        Args:
            location (str): Строка локации
            
        Returns:
            bool: True если локация валидная
        """
        if not isinstance(location, str):
            return False
        
        # Проверяем базовый формат: "Город, Штат" или "Город, Страна"
        parts = location.split(', ')
        return len(parts) >= 2 and all(part.strip() for part in parts)


class RoleInfoExtractor:
    """Класс для извлечения информации о ролях танцоров"""
    
    def __init__(self):
        self.cleaner = DataCleaner()
    
    def extract_role_info(self, dancer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Извлечение информации о роли танцора
        
        Args:
            dancer_data (dict): Данные танцора
            
        Returns:
            dict: Обработанные данные о роли
            
        Raises:
            ValidationError: Если данные некорректны
        """
        try:
            if not isinstance(dancer_data, dict):
                raise ValidationError("dancer_data должен быть словарем")
            
            # Очистка имени
            dancer_data['dancer_first'] = self.cleaner.clean_text(
                dancer_data.get('dancer_first', '')
            )
            dancer_data['dancer_last'] = self.cleaner.clean_text(
                dancer_data.get('dancer_last', '')
            )
            
            # Валидация ID
            dancer_id = dancer_data.get('dancer_wsdcid')
            if not self.cleaner.validate_dancer_id(dancer_id):
                raise ValidationError(f"Неверный ID танцора: {dancer_id}")
            
            # Обработка ролей
            processed_data = {
                'dancer_id': int(dancer_id),
                'dancer_first': dancer_data['dancer_first'],
                'dancer_last': dancer_data['dancer_last'],
                'dancer_name': f"{dancer_data['dancer_first']} {dancer_data['dancer_last']}".strip(),
                'update_date': datetime.now().strftime('%Y-%m-%d'),
                'dominate_role': dancer_data.get('dominate_role', ''),
                'non_dominate_role': dancer_data.get('non_dominate_role', ''),
                'dominate_required': dancer_data.get('dominate_required', ''),
                'dominate_allowed': dancer_data.get('dominate_allowed', ''),
                'non_dominate_required': dancer_data.get('non_dominate_required', ''),
                'non_dominate_allowed': dancer_data.get('non_dominate_allowed', '')
            }
            
            logger.debug(f"Обработана информация о роли для танцора {dancer_id}")
            return processed_data
            
        except Exception as e:
            logger.error(f"Ошибка при извлечении информации о роли: {e}")
            raise ValidationError(f"Ошибка обработки данных танцора: {e}")


class LocationExtractor:
    """Класс для извлечения географической информации"""
    
    def __init__(self):
        self.cleaner = DataCleaner()
    
    def extract_state(self, location: str) -> Optional[str]:
        """
        Извлечение штата из строки локации
        
        Args:
            location (str): Строка локации
            
        Returns:
            str or None: Код штата или None
        """
        try:
            if not self.cleaner.validate_location(location):
                return None

            from transform.geography import (  # noqa: WPS433
                parse_us_state_from_location_text,
            )
            from transform.geography.constants import STATE_NAME_TO_CODE  # noqa: WPS433

            full_name = parse_us_state_from_location_text(location)
            if full_name:
                return STATE_NAME_TO_CODE.get(full_name)

            parts = location.split(', ')
            if len(parts) == 2 and len(parts[1]) == 2:
                return parts[1].upper()
            return None
            
        except Exception as e:
            logger.warning(f"Ошибка при извлечении штата из '{location}': {e}")
            return None
    
    def extract_country(self, location: str) -> Optional[str]:
        """
        Извлечение страны из строки локации
        
        Args:
            location (str): Строка локации
            
        Returns:
            str or None: Название страны или None
        """
        try:
            if not self.cleaner.validate_location(location):
                return None
            
            parts = location.split(', ')
            if len(parts) == 2:
                if len(parts[1]) == 2:
                    return 'United States'
                else:
                    return parts[1].strip()
            return None
            
        except Exception as e:
            logger.warning(f"Ошибка при извлечении страны из '{location}': {e}")
            return None
    
    def extract_city(self, location: str) -> Optional[str]:
        """
        Извлечение города из строки локации
        
        Args:
            location (str): Строка локации
            
        Returns:
            str or None: Название города или None
        """
        try:
            if not self.cleaner.validate_location(location):
                return None
            
            parts = location.split(', ')
            return parts[0].strip() if parts else None
            
        except Exception as e:
            logger.warning(f"Ошибка при извлечении города из '{location}': {e}")
            return None
    
    def extract_coordinates(self, location: str) -> Optional[Dict[str, float]]:
        """
        Извлечение координат (заглушка для будущей интеграции с геокодингом)
        
        Args:
            location (str): Строка локации
            
        Returns:
            dict or None: Словарь с координатами или None
        """
        # TODO: Интеграция с Google Maps API или Nominatim
        logger.debug(f"Запрос координат для локации: {location}")
        return None


class DateExtractor:
    """Класс для извлечения и обработки дат"""
    
    @staticmethod
    def extract_month(date_str: str) -> Optional[str]:
        """
        Извлечение месяца из строки даты
        
        Args:
            date_str (str): Строка с датой
            
        Returns:
            str or None: Название месяца или None
        """
        try:
            if not isinstance(date_str, str):
                return None
            
            parts = date_str.split(' ')
            return parts[0] if parts else None
            
        except Exception as e:
            logger.warning(f"Ошибка при извлечении месяца из '{date_str}': {e}")
            return None
    
    @staticmethod
    def extract_year(date_str: str) -> Optional[int]:
        """
        Извлечение года из строки даты
        
        Args:
            date_str (str): Строка с датой
            
        Returns:
            int or None: Год или None
        """
        try:
            if not isinstance(date_str, str):
                return None
            
            parts = date_str.split(' ')
            if len(parts) >= 2:
                year = int(parts[1])
                # Проверяем разумность года
                if 1900 <= year <= 2100:
                    return year
            return None
            
        except (ValueError, IndexError) as e:
            logger.warning(f"Ошибка при извлечении года из '{date_str}': {e}")
            return None
    
    @staticmethod
    def parse_date(date_str: str) -> Optional[datetime]:
        """
        Парсинг даты в объект datetime
        
        Args:
            date_str (str): Строка с датой
            
        Returns:
            datetime or None: Объект datetime или None
        """
        try:
            if not isinstance(date_str, str):
                return None
            
            # Попробуем разные форматы дат
            formats = [
                '%Y-%m-%d',
                '%m/%d/%Y',
                '%d/%m/%Y',
                '%B %Y',
                '%Y'
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            return None
            
        except Exception as e:
            logger.warning(f"Ошибка при парсинге даты '{date_str}': {e}")
            return None


class ResultsExtractor:
    """Класс для извлечения результатов соревнований"""
    
    def __init__(self):
        self.cleaner = DataCleaner()
    
    def extract_dancer_results(self, soup_list: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Извлечение результатов танцоров
        
        Args:
            soup_list (list): Список данных танцоров
            
        Returns:
            pd.DataFrame: DataFrame с результатами
            
        Raises:
            ValidationError: Если данные некорректны
        """
        try:
            if not isinstance(soup_list, list):
                raise ValidationError("soup_list должен быть списком")
            
            dancer_results = []
            
            for soup in soup_list:
                try:
                    dancer_id = soup.get('dancer_wsdcid')
                    if not self.cleaner.validate_dancer_id(dancer_id):
                        logger.warning(f"Пропущен неверный ID танцора: {dancer_id}")
                        continue
                    
                    # Извлечение событий
                    events = soup.get('events', [])
                    if not isinstance(events, list):
                        continue
                    
                    for event in events:
                        if isinstance(event, dict):
                            result_data = {
                                'dancer_id': int(dancer_id),
                                'event_dance': event.get('dance', ''),
                                'event_competition': event.get('competition', ''),
                                'event_role': event.get('role', ''),
                                'event_location': event.get('location', ''),
                                'event_name_id': event.get('name_id', ''),
                                'event_name': event.get('name', ''),
                                'event_date': event.get('date', ''),
                                'event_result': event.get('result', ''),
                                'event_points': event.get('points', 0)
                            }
                            dancer_results.append(result_data)
                    
                except Exception as e:
                    logger.warning(f"Ошибка при обработке танцора {dancer_id}: {e}")
                    continue
            
            # Создание DataFrame
            columns = [
                'dancer_id', 'event_dance', 'event_competition', 'event_role',
                'event_location', 'event_name_id', 'event_name', 'event_date',
                'event_result', 'event_points'
            ]
            
            df = pd.DataFrame(dancer_results, columns=columns)
            logger.info(f"Извлечено {len(df)} результатов для {len(soup_list)} танцоров")
            return df
            
        except Exception as e:
            logger.error(f"Ошибка при извлечении результатов: {e}")
            raise ValidationError(f"Ошибка обработки результатов: {e}")


class TransitionAnalyzer:
    """Класс для анализа переходов между дивизионами"""
    
    DIVISIONS = ['Novice', 'Intermediate', 'Advanced', 'All-Star', 'Champion']
    
    @staticmethod
    def determine_transition(prev: str, curr: str) -> Optional[str]:
        """
        Определение типа перехода между дивизионами
        
        Args:
            prev (str): Предыдущий дивизион
            curr (str): Текущий дивизион
            
        Returns:
            str or None: Тип перехода или None
        """
        try:
            if prev not in TransitionAnalyzer.DIVISIONS or curr not in TransitionAnalyzer.DIVISIONS:
                return None
            
            prev_index = TransitionAnalyzer.DIVISIONS.index(prev)
            curr_index = TransitionAnalyzer.DIVISIONS.index(curr)
            
            if curr_index > prev_index:
                return 'promotion'
            elif curr_index < prev_index:
                return 'demotion'
            else:
                return 'no_change'
                
        except Exception as e:
            logger.warning(f"Ошибка при определении перехода {prev} -> {curr}: {e}")
            return None
    
    @staticmethod
    def analyze_transitions(df: pd.DataFrame) -> pd.DataFrame:
        """
        Анализ переходов в DataFrame
        
        Args:
            df (pd.DataFrame): DataFrame с данными о дивизионах
            
        Returns:
            pd.DataFrame: DataFrame с анализом переходов
        """
        try:
            if df.empty:
                return pd.DataFrame()
            
            # Сортировка по танцору и дате
            df_sorted = df.sort_values(['dancer_id', 'update_date'])
            
            transitions = []
            
            for dancer_id in df_sorted['dancer_id'].unique():
                dancer_data = df_sorted[df_sorted['dancer_id'] == dancer_id]
                
                if len(dancer_data) < 2:
                    continue
                
                for i in range(1, len(dancer_data)):
                    prev_row = dancer_data.iloc[i-1]
                    curr_row = dancer_data.iloc[i]
                    
                    transition_type = TransitionAnalyzer.determine_transition(
                        prev_row['dominate_role'], 
                        curr_row['dominate_role']
                    )
                    
                    if transition_type:
                        transition_data = {
                            'dancer_id': dancer_id,
                            'update_date': curr_row['update_date'],
                            'previous_division': prev_row['dominate_role'],
                            'current_division': curr_row['dominate_role'],
                            'transition_type': transition_type
                        }
                        transitions.append(transition_data)
            
            result_df = pd.DataFrame(transitions)
            logger.info(f"Проанализировано {len(result_df)} переходов")
            return result_df
            
        except Exception as e:
            logger.error(f"Ошибка при анализе переходов: {e}")
            return pd.DataFrame()


# Фабрика для создания экземпляров классов
class DataProcessorFactory:
    """Фабрика для создания процессоров данных"""
    
    @staticmethod
    def create_role_extractor() -> RoleInfoExtractor:
        """Создание экземпляра RoleInfoExtractor"""
        return RoleInfoExtractor()
    
    @staticmethod
    def create_location_extractor() -> LocationExtractor:
        """Создание экземпляра LocationExtractor"""
        return LocationExtractor()
    
    @staticmethod
    def create_date_extractor() -> DateExtractor:
        """Создание экземпляра DateExtractor"""
        return DateExtractor()
    
    @staticmethod
    def create_results_extractor() -> ResultsExtractor:
        """Создание экземпляра ResultsExtractor"""
        return ResultsExtractor()
    
    @staticmethod
    def create_transition_analyzer() -> TransitionAnalyzer:
        """Создание экземпляра TransitionAnalyzer"""
        return TransitionAnalyzer()


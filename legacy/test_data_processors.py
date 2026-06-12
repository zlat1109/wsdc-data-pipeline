"""
Tests for Data Processors Module
Тесты для модулей обработки данных WSDC
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime
from data_processors import (
    DataCleaner,
    RoleInfoExtractor,
    LocationExtractor,
    DateExtractor,
    ResultsExtractor,
    TransitionAnalyzer
)


class TestDataCleaner(unittest.TestCase):
    """Тесты для класса DataCleaner"""
    
    def setUp(self):
        self.cleaner = DataCleaner()
    
    def test_clean_text(self):
        """Тест очистки текста"""
        # Тест с табуляцией
        self.assertEqual(self.cleaner.clean_text("John\tDoe"), "John Doe")
        
        # Тест с множественными пробелами
        self.assertEqual(self.cleaner.clean_text("John   Doe"), "John Doe")
        
        # Тест с пустой строкой
        self.assertEqual(self.cleaner.clean_text(""), "")
        
        # Тест с None
        self.assertEqual(self.cleaner.clean_text(None), "")
    
    def test_validate_dancer_id(self):
        """Тест валидации ID танцора"""
        # Валидные ID
        self.assertTrue(self.cleaner.validate_dancer_id(12345))
        self.assertTrue(self.cleaner.validate_dancer_id("12345"))
        
        # Невалидные ID
        self.assertFalse(self.cleaner.validate_dancer_id(0))
        self.assertFalse(self.cleaner.validate_dancer_id(-1))
        self.assertFalse(self.cleaner.validate_dancer_id("abc"))
        self.assertFalse(self.cleaner.validate_dancer_id(None))
    
    def test_validate_location(self):
        """Тест валидации локации"""
        # Валидные локации
        self.assertTrue(self.cleaner.validate_location("New York, NY"))
        self.assertTrue(self.cleaner.validate_location("London, UK"))
        
        # Невалидные локации
        self.assertFalse(self.cleaner.validate_location("New York"))
        self.assertFalse(self.cleaner.validate_location(""))
        self.assertFalse(self.cleaner.validate_location(None))


class TestRoleInfoExtractor(unittest.TestCase):
    """Тесты для класса RoleInfoExtractor"""
    
    def setUp(self):
        self.extractor = RoleInfoExtractor()
    
    def test_extract_role_info_valid(self):
        """Тест извлечения информации о роли с валидными данными"""
        dancer_data = {
            'dancer_wsdcid': '12345',
            'dancer_first': 'John\t',
            'dancer_last': '  Doe  ',
            'dominate_role': 'Lead',
            'non_dominate_role': 'Follow',
            'dominate_required': 'Advanced',
            'dominate_allowed': 'All-Star'
        }
        
        result = self.extractor.extract_role_info(dancer_data)
        
        self.assertEqual(result['dancer_id'], 12345)
        self.assertEqual(result['dancer_first'], 'John')
        self.assertEqual(result['dancer_last'], 'Doe')
        self.assertEqual(result['dancer_name'], 'John Doe')
        self.assertEqual(result['dominate_role'], 'Lead')
    
    def test_extract_role_info_invalid_id(self):
        """Тест с невалидным ID"""
        dancer_data = {
            'dancer_wsdcid': 'invalid',
            'dancer_first': 'John',
            'dancer_last': 'Doe'
        }
        
        with self.assertRaises(Exception):
            self.extractor.extract_role_info(dancer_data)
    
    def test_extract_role_info_missing_data(self):
        """Тест с отсутствующими данными"""
        dancer_data = {
            'dancer_wsdcid': '12345'
        }
        
        result = self.extractor.extract_role_info(dancer_data)
        self.assertEqual(result['dancer_first'], '')
        self.assertEqual(result['dancer_last'], '')


class TestLocationExtractor(unittest.TestCase):
    """Тесты для класса LocationExtractor"""
    
    def setUp(self):
        self.extractor = LocationExtractor()
    
    def test_extract_state(self):
        """Тест извлечения штата"""
        # Валидные случаи
        self.assertEqual(self.extractor.extract_state("New York, NY"), "NY")
        self.assertEqual(self.extractor.extract_state("Los Angeles, CA"), "CA")
        
        # Невалидные случаи
        self.assertIsNone(self.extractor.extract_state("New York"))
        self.assertIsNone(self.extractor.extract_state("New York, USA"))
        self.assertIsNone(self.extractor.extract_state(""))
    
    def test_extract_country(self):
        """Тест извлечения страны"""
        # США (по коду штата)
        self.assertEqual(self.extractor.extract_country("New York, NY"), "United States")
        
        # Другие страны
        self.assertEqual(self.extractor.extract_country("London, UK"), "UK")
        self.assertEqual(self.extractor.extract_country("Paris, France"), "France")
        
        # Невалидные случаи
        self.assertIsNone(self.extractor.extract_country("New York"))
        self.assertIsNone(self.extractor.extract_country(""))
    
    def test_extract_city(self):
        """Тест извлечения города"""
        self.assertEqual(self.extractor.extract_city("New York, NY"), "New York")
        self.assertEqual(self.extractor.extract_city("Los Angeles, CA"), "Los Angeles")
        self.assertIsNone(self.extractor.extract_city(""))


class TestDateExtractor(unittest.TestCase):
    """Тесты для класса DateExtractor"""
    
    def test_extract_month(self):
        """Тест извлечения месяца"""
        self.assertEqual(DateExtractor.extract_month("January 2023"), "January")
        self.assertEqual(DateExtractor.extract_month("Dec 2022"), "Dec")
        self.assertIsNone(DateExtractor.extract_month(""))
        self.assertIsNone(DateExtractor.extract_month(None))
    
    def test_extract_year(self):
        """Тест извлечения года"""
        self.assertEqual(DateExtractor.extract_year("January 2023"), 2023)
        self.assertEqual(DateExtractor.extract_year("Dec 2022"), 2022)
        
        # Невалидные случаи
        self.assertIsNone(DateExtractor.extract_year("January"))
        self.assertIsNone(DateExtractor.extract_year("January 1800"))  # Слишком старый год
        self.assertIsNone(DateExtractor.extract_year("January 2200"))  # Слишком новый год
    
    def test_parse_date(self):
        """Тест парсинга даты"""
        # Валидные форматы
        self.assertIsNotNone(DateExtractor.parse_date("2023-01-15"))
        self.assertIsNotNone(DateExtractor.parse_date("01/15/2023"))
        
        # Невалидные форматы
        self.assertIsNone(DateExtractor.parse_date("invalid"))
        self.assertIsNone(DateExtractor.parse_date(""))


class TestResultsExtractor(unittest.TestCase):
    """Тесты для класса ResultsExtractor"""
    
    def setUp(self):
        self.extractor = ResultsExtractor()
    
    def test_extract_dancer_results_valid(self):
        """Тест извлечения результатов с валидными данными"""
        soup_list = [
            {
                'dancer_wsdcid': '12345',
                'events': [
                    {
                        'dance': 'West Coast Swing',
                        'competition': 'Advanced',
                        'role': 'Lead',
                        'location': 'New York, NY',
                        'name': 'Test Event',
                        'date': '2023-01-15',
                        'result': '1st Place',
                        'points': 100
                    }
                ]
            }
        ]
        
        result = self.extractor.extract_dancer_results(soup_list)
        
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]['dancer_id'], 12345)
        self.assertEqual(result.iloc[0]['event_dance'], 'West Coast Swing')
    
    def test_extract_dancer_results_invalid_id(self):
        """Тест с невалидным ID"""
        soup_list = [
            {
                'dancer_wsdcid': 'invalid',
                'events': []
            }
        ]
        
        result = self.extractor.extract_dancer_results(soup_list)
        self.assertEqual(len(result), 0)
    
    def test_extract_dancer_results_empty_events(self):
        """Тест с пустыми событиями"""
        soup_list = [
            {
                'dancer_wsdcid': '12345',
                'events': []
            }
        ]
        
        result = self.extractor.extract_dancer_results(soup_list)
        self.assertEqual(len(result), 0)


class TestTransitionAnalyzer(unittest.TestCase):
    """Тесты для класса TransitionAnalyzer"""
    
    def test_determine_transition(self):
        """Тест определения типа перехода"""
        # Повышение
        self.assertEqual(
            TransitionAnalyzer.determine_transition('Novice', 'Intermediate'),
            'promotion'
        )
        
        # Понижение
        self.assertEqual(
            TransitionAnalyzer.determine_transition('Advanced', 'Intermediate'),
            'demotion'
        )
        
        # Без изменений
        self.assertEqual(
            TransitionAnalyzer.determine_transition('Advanced', 'Advanced'),
            'no_change'
        )
        
        # Невалидные дивизионы
        self.assertIsNone(
            TransitionAnalyzer.determine_transition('Invalid', 'Advanced')
        )
    
    def test_analyze_transitions(self):
        """Тест анализа переходов"""
        # Создаем тестовые данные
        data = [
            {'dancer_id': 1, 'update_date': '2023-01-01', 'dominate_role': 'Novice'},
            {'dancer_id': 1, 'update_date': '2023-02-01', 'dominate_role': 'Intermediate'},
            {'dancer_id': 2, 'update_date': '2023-01-01', 'dominate_role': 'Advanced'},
            {'dancer_id': 2, 'update_date': '2023-02-01', 'dominate_role': 'Advanced'},
        ]
        
        df = pd.DataFrame(data)
        result = TransitionAnalyzer.analyze_transitions(df)
        
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 1)  # Только один переход
        self.assertEqual(result.iloc[0]['transition_type'], 'promotion')


class TestDataProcessorFactory(unittest.TestCase):
    """Тесты для фабрики процессоров данных"""
    
    def test_create_role_extractor(self):
        """Тест создания RoleInfoExtractor"""
        extractor = DataProcessorFactory.create_role_extractor()
        self.assertIsInstance(extractor, RoleInfoExtractor)
    
    def test_create_location_extractor(self):
        """Тест создания LocationExtractor"""
        extractor = DataProcessorFactory.create_location_extractor()
        self.assertIsInstance(extractor, LocationExtractor)
    
    def test_create_date_extractor(self):
        """Тест создания DateExtractor"""
        extractor = DataProcessorFactory.create_date_extractor()
        self.assertIsInstance(extractor, DateExtractor)
    
    def test_create_results_extractor(self):
        """Тест создания ResultsExtractor"""
        extractor = DataProcessorFactory.create_results_extractor()
        self.assertIsInstance(extractor, ResultsExtractor)
    
    def test_create_transition_analyzer(self):
        """Тест создания TransitionAnalyzer"""
        analyzer = DataProcessorFactory.create_transition_analyzer()
        self.assertIsInstance(analyzer, TransitionAnalyzer)


if __name__ == '__main__':
    # Запуск всех тестов
    unittest.main(verbosity=2)


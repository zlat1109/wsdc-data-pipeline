"""
Tests for Data Analytics Module
Тесты для модуля аналитики данных WSDC
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime
import tempfile
import os
from unittest.mock import Mock, patch

from parser.data_analytics import DataAnalyzer, DataVisualizer, ReportGenerator


class TestDataAnalyzer(unittest.TestCase):
    """Тесты для класса DataAnalyzer"""
    
    def setUp(self):
        """Настройка тестовых данных"""
        self.analyzer = DataAnalyzer()
        
        # Тестовые данные
        self.test_df = pd.DataFrame({
            'dancer_id': [1, 2, 3, 4, 5],
            'dominate_role': ['Novice', 'Intermediate', 'Advanced', 'Novice', 'Intermediate'],
            'event_location': ['New York, NY', 'Los Angeles, CA', 'Chicago, IL', 'Miami, FL', 'Seattle, WA'],
            'event_country': ['United States', 'United States', 'United States', 'United States', 'United States'],
            'event_state': ['NY', 'CA', 'IL', 'FL', 'WA'],
            'event_city': ['New York', 'Los Angeles', 'Chicago', 'Miami', 'Seattle'],
            'event_year': [2020, 2021, 2022, 2021, 2022],
            'event_month': ['January', 'February', 'March', 'April', 'May'],
            'event_points': [100, 150, 200, 120, 180],
            'event_result': ['1st Place', '2nd Place', '3rd Place', '1st Place', '2nd Place']
        })
    
    def test_analyze_dancer_distribution(self):
        """Тест анализа распределения танцоров"""
        stats = self.analyzer.analyze_dancer_distribution(self.test_df)
        
        self.assertIsInstance(stats, dict)
        self.assertEqual(stats['total_dancers'], 5)
        self.assertEqual(stats['unique_divisions'], 3)
        self.assertIn('division_counts', stats)
        self.assertIn('division_percentages', stats)
    
    def test_analyze_dancer_distribution_empty_df(self):
        """Тест с пустым DataFrame"""
        empty_df = pd.DataFrame()
        stats = self.analyzer.analyze_dancer_distribution(empty_df)
        self.assertEqual(stats, {})
    
    def test_analyze_geographic_distribution(self):
        """Тест анализа географического распределения"""
        stats = self.analyzer.analyze_geographic_distribution(self.test_df)
        
        self.assertIsInstance(stats, dict)
        self.assertIn('country_distribution', stats)
        self.assertIn('state_distribution', stats)
        self.assertIn('city_distribution', stats)
        
        country_stats = stats['country_distribution']
        self.assertEqual(country_stats['total_countries'], 1)
        self.assertEqual(country_stats['most_active_country'], 'United States')
    
    def test_analyze_temporal_trends(self):
        """Тест анализа временных трендов"""
        stats = self.analyzer.analyze_temporal_trends(self.test_df)
        
        self.assertIsInstance(stats, dict)
        self.assertIn('yearly_trends', stats)
        self.assertIn('monthly_trends', stats)
        
        yearly_stats = stats['yearly_trends']
        self.assertEqual(yearly_stats['year_range'], '2020 - 2022')
    
    def test_analyze_performance_metrics(self):
        """Тест анализа метрик производительности"""
        stats = self.analyzer.analyze_performance_metrics(self.test_df)
        
        self.assertIsInstance(stats, dict)
        self.assertIn('points_analysis', stats)
        self.assertIn('result_analysis', stats)
        
        points_stats = stats['points_analysis']
        self.assertIn('mean_points', points_stats)
        self.assertIn('max_points', points_stats)
    
    @patch('data_analytics.googlemaps.Client')
    def test_get_coordinates_google_maps(self, mock_gmaps):
        """Тест получения координат через Google Maps API"""
        # Мокаем ответ Google Maps API
        mock_gmaps.return_value.geocode.return_value = [{
            'geometry': {
                'location': {
                    'lat': 40.7128,
                    'lng': -74.0060
                }
            }
        }]
        
        coords = self.analyzer.get_coordinates("New York, NY")
        self.assertIsNotNone(coords)
        self.assertEqual(coords['latitude'], 40.7128)
        self.assertEqual(coords['longitude'], -74.0060)
    
    def test_get_coordinates_invalid_location(self):
        """Тест с невалидной локацией"""
        coords = self.analyzer.get_coordinates("")
        self.assertIsNone(coords)
        
        coords = self.analyzer.get_coordinates(None)
        self.assertIsNone(coords)


class TestDataVisualizer(unittest.TestCase):
    """Тесты для класса DataVisualizer"""
    
    def setUp(self):
        """Настройка тестовых данных"""
        self.visualizer = DataVisualizer()
        
        # Тестовые данные
        self.test_df = pd.DataFrame({
            'dancer_id': [1, 2, 3, 4, 5],
            'dominate_role': ['Novice', 'Intermediate', 'Advanced', 'Novice', 'Intermediate'],
            'event_location': ['New York, NY', 'Los Angeles, CA', 'Chicago, IL', 'Miami, FL', 'Seattle, WA'],
            'event_year': [2020, 2021, 2022, 2021, 2022],
            'event_month': ['January', 'February', 'March', 'April', 'May'],
            'event_points': [100, 150, 200, 120, 180],
            'event_result': ['1st Place', '2nd Place', '3rd Place', '1st Place', '2nd Place']
        })
    
    def test_create_division_distribution_chart(self):
        """Тест создания графика распределения по дивизионам"""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            chart = self.visualizer.create_division_distribution_chart(self.test_df, tmp_file.name)
            
            self.assertIsNotNone(chart)
            self.assertTrue(os.path.exists(tmp_file.name))
            
            # Очистка
            os.unlink(tmp_file.name)
    
    def test_create_division_distribution_chart_no_data(self):
        """Тест с пустыми данными"""
        empty_df = pd.DataFrame()
        chart = self.visualizer.create_division_distribution_chart(empty_df)
        self.assertIsNone(chart)
    
    def test_create_temporal_analysis_chart(self):
        """Тест создания графика временного анализа"""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            chart = self.visualizer.create_temporal_analysis_chart(self.test_df, tmp_file.name)
            
            self.assertIsNotNone(chart)
            self.assertTrue(os.path.exists(tmp_file.name))
            
            # Очистка
            os.unlink(tmp_file.name)
    
    def test_create_performance_analysis_chart(self):
        """Тест создания графика анализа производительности"""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            chart = self.visualizer.create_performance_analysis_chart(self.test_df, tmp_file.name)
            
            self.assertIsNotNone(chart)
            self.assertTrue(os.path.exists(tmp_file.name))
            
            # Очистка
            os.unlink(tmp_file.name)
    
    def test_create_interactive_dashboard(self):
        """Тест создания интерактивной панели"""
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as tmp_file:
            dashboard = self.visualizer.create_interactive_dashboard(self.test_df, tmp_file.name)
            
            self.assertIsNotNone(dashboard)
            self.assertTrue(os.path.exists(tmp_file.name))
            
            # Очистка
            os.unlink(tmp_file.name)
    
    def test_create_interactive_dashboard_no_data(self):
        """Тест с пустыми данными"""
        empty_df = pd.DataFrame()
        dashboard = self.visualizer.create_interactive_dashboard(empty_df)
        self.assertIsNone(dashboard)


class TestReportGenerator(unittest.TestCase):
    """Тесты для класса ReportGenerator"""
    
    def setUp(self):
        """Настройка тестовых данных"""
        self.generator = ReportGenerator()
        
        # Тестовые данные
        self.test_df = pd.DataFrame({
            'dancer_id': [1, 2, 3, 4, 5],
            'dominate_role': ['Novice', 'Intermediate', 'Advanced', 'Novice', 'Intermediate'],
            'event_location': ['New York, NY', 'Los Angeles, CA', 'Chicago, IL', 'Miami, FL', 'Seattle, WA'],
            'event_country': ['United States', 'United States', 'United States', 'United States', 'United States'],
            'event_state': ['NY', 'CA', 'IL', 'FL', 'WA'],
            'event_city': ['New York', 'Los Angeles', 'Chicago', 'Miami', 'Seattle'],
            'event_year': [2020, 2021, 2022, 2021, 2022],
            'event_month': ['January', 'February', 'March', 'April', 'May'],
            'event_points': [100, 150, 200, 120, 180],
            'event_result': ['1st Place', '2nd Place', '3rd Place', '1st Place', '2nd Place']
        })
    
    def test_generate_comprehensive_report(self):
        """Тест генерации комплексного отчета"""
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = self.generator.generate_comprehensive_report(self.test_df, temp_dir)
            
            self.assertIsInstance(report_path, str)
            self.assertTrue(os.path.exists(report_path))
            self.assertTrue(report_path.endswith('.html'))
            
            # Проверяем содержимое отчета
            with open(report_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn('WSDC Data Analysis Report', content)
                self.assertIn('Total records: 5', content)
    
    def test_generate_comprehensive_report_empty_df(self):
        """Тест с пустыми данными"""
        empty_df = pd.DataFrame()
        report_path = self.generator.generate_comprehensive_report(empty_df)
        self.assertEqual(report_path, "")
    
    def test_create_html_report(self):
        """Тест создания HTML отчета"""
        division_stats = {'total_dancers': 5, 'unique_divisions': 3}
        geo_stats = {'country_distribution': {'total_countries': 1}}
        temporal_stats = {'yearly_trends': {'year_range': '2020 - 2022'}}
        performance_stats = {'points_analysis': {'mean_points': 150}}
        
        html_content = self.generator._create_html_report(
            self.test_df, division_stats, geo_stats, temporal_stats, performance_stats, 'test'
        )
        
        self.assertIsInstance(html_content, str)
        self.assertIn('WSDC Data Analysis Report', html_content)
        self.assertIn('Total records: 5', html_content)
        self.assertIn('Total Dancers: 5', html_content)


class TestIntegration(unittest.TestCase):
    """Интеграционные тесты"""
    
    def setUp(self):
        """Настройка тестовых данных"""
        self.analyzer = DataAnalyzer()
        self.visualizer = DataVisualizer()
        self.generator = ReportGenerator()
        
        # Большой тестовый набор данных
        np.random.seed(42)
        n_records = 100
        
        self.large_df = pd.DataFrame({
            'dancer_id': range(1, n_records + 1),
            'dominate_role': np.random.choice(['Novice', 'Intermediate', 'Advanced', 'All-Star'], n_records),
            'event_location': np.random.choice([
                'New York, NY', 'Los Angeles, CA', 'Chicago, IL', 'Miami, FL', 'Seattle, WA',
                'Boston, MA', 'Denver, CO', 'Austin, TX', 'Portland, OR', 'Nashville, TN'
            ], n_records),
            'event_year': np.random.randint(2018, 2024, n_records),
            'event_month': np.random.choice([
                'January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'
            ], n_records),
            'event_points': np.random.randint(50, 300, n_records),
            'event_result': np.random.choice(['1st Place', '2nd Place', '3rd Place', '4th Place', '5th Place'], n_records)
        })
    
    def test_full_analysis_pipeline(self):
        """Тест полного пайплайна анализа"""
        # Анализ данных
        division_stats = self.analyzer.analyze_dancer_distribution(self.large_df)
        geo_stats = self.analyzer.analyze_geographic_distribution(self.large_df)
        temporal_stats = self.analyzer.analyze_temporal_trends(self.large_df)
        performance_stats = self.analyzer.analyze_performance_metrics(self.large_df)
        
        # Проверяем результаты
        self.assertEqual(division_stats['total_dancers'], 100)
        self.assertGreater(len(geo_stats), 0)
        self.assertGreater(len(temporal_stats), 0)
        self.assertGreater(len(performance_stats), 0)
    
    def test_full_visualization_pipeline(self):
        """Тест полного пайплайна визуализации"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Создание графиков
            division_chart = self.visualizer.create_division_distribution_chart(
                self.large_df, os.path.join(temp_dir, 'division.png')
            )
            temporal_chart = self.visualizer.create_temporal_analysis_chart(
                self.large_df, os.path.join(temp_dir, 'temporal.png')
            )
            performance_chart = self.visualizer.create_performance_analysis_chart(
                self.large_df, os.path.join(temp_dir, 'performance.png')
            )
            
            # Проверяем, что графики созданы
            self.assertIsNotNone(division_chart)
            self.assertIsNotNone(temporal_chart)
            self.assertIsNotNone(performance_chart)
            
            # Проверяем, что файлы сохранены
            self.assertTrue(os.path.exists(os.path.join(temp_dir, 'division.png')))
            self.assertTrue(os.path.exists(os.path.join(temp_dir, 'temporal.png')))
            self.assertTrue(os.path.exists(os.path.join(temp_dir, 'performance.png')))
    
    def test_full_report_generation(self):
        """Тест полной генерации отчета"""
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = self.generator.generate_comprehensive_report(self.large_df, temp_dir)
            
            self.assertIsInstance(report_path, str)
            self.assertTrue(os.path.exists(report_path))
            
            # Проверяем, что все файлы отчета созданы
            report_dir = os.path.dirname(report_path)
            files = os.listdir(report_dir)
            
            # Должны быть HTML отчет и графики
            html_files = [f for f in files if f.endswith('.html')]
            png_files = [f for f in files if f.endswith('.png')]
            
            self.assertGreater(len(html_files), 0)
            self.assertGreater(len(png_files), 0)


if __name__ == '__main__':
    # Запуск всех тестов
    unittest.main(verbosity=2)


"""
WSDC Points Parser - Улучшенная версия
Анализ данных танцоров World Swing Dance Championships
"""

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
from dotenv import load_dotenv
import os

# Импортируем наши улучшения
from config import Config
from exceptions import TokenNotFoundError, DancerNotFoundError, NetworkError, ValidationError
from logger import logger
from data_processors import (
    DataProcessorFactory, 
    RoleInfoExtractor, 
    LocationExtractor, 
    DateExtractor, 
    ResultsExtractor, 
    TransitionAnalyzer
)
from data_analytics import DataAnalyzer, DataVisualizer, ReportGenerator

# Загружаем переменные окружения
load_dotenv()

class WSDCParser:
    """Основной класс для парсинга данных WSDC"""
    
    def __init__(self):
        """Инициализация парсера"""
        self.config = Config()
        self.session = requests.Session()
        self.driver = None
        
        # Инициализация процессоров данных
        self.role_extractor = DataProcessorFactory.create_role_extractor()
        self.location_extractor = DataProcessorFactory.create_location_extractor()
        self.date_extractor = DataProcessorFactory.create_date_extractor()
        self.results_extractor = DataProcessorFactory.create_results_extractor()
        self.transition_analyzer = DataProcessorFactory.create_transition_analyzer()
        
        # Инициализация модулей аналитики
        self.data_analyzer = DataAnalyzer()
        self.data_visualizer = DataVisualizer()
        self.report_generator = ReportGenerator()
        
        self.setup_driver()
        self.setup_session()
        
    def setup_driver(self):
        """Настройка веб-драйвера Chrome"""
        try:
            chrome_options = Options()
            for option in self.config.CHROME_OPTIONS:
                chrome_options.add_argument(option)
            
            self.driver = webdriver.Chrome(options=chrome_options)
            logger.info("Веб-драйвер Chrome успешно инициализирован")
        except Exception as e:
            logger.error(f"Ошибка при инициализации веб-драйвера: {e}")
            raise
    
    def setup_session(self):
        """Настройка HTTP сессии"""
        try:
            # Отключаем предупреждения о небезопасных запросах
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            # Настройка сессии
            self.session.headers.update(self.config.HEADERS)
            logger.info("HTTP сессия успешно настроена")
        except Exception as e:
            logger.error(f"Ошибка при настройке HTTP сессии: {e}")
            raise
    
    def check_id(self, dancer_id):
        """
        Проверка существования танцора по ID
        
        Args:
            dancer_id (int): ID танцора
            
        Returns:
            bool: True если танцор найден, False в противном случае
        """
        try:
            if not isinstance(dancer_id, int) or dancer_id <= 0:
                raise ValidationError(f"Неверный ID танцора: {dancer_id}")
            
            url = f"{self.config.CHECK_CONTESTERS_URL}{dancer_id}"
            response = self.session.get(
                url,
                headers=self.config.CHECK_CONTESTERS_HEADERS,
                verify=self.config.VERIFY_SSL,
                timeout=self.config.TIMEOUT
            )
            response.raise_for_status()
            
            return response.text != '[]'
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при проверке ID {dancer_id}: {e}")
            raise NetworkError(f"Ошибка сети при проверке ID {dancer_id}") from e
        except Exception as e:
            logger.error(f"Неожиданная ошибка при проверке ID {dancer_id}: {e}")
            raise
    
    def get_token(self):
        """
        Получение CSRF токена
        
        Returns:
            str: CSRF токен
            
        Raises:
            TokenNotFoundError: Если токен не найден
        """
        try:
            response = self.session.get(
                self.config.TOKEN_URL,
                headers=self.config.TOKEN_HEADERS,
                verify=self.config.VERIFY_SSL,
                timeout=self.config.TIMEOUT
            )
            response.raise_for_status()
            
            # Поиск токена в HTML
            match = re.search(r'name="_token" value="(.*?)"', response.text)
            if not match:
                raise TokenNotFoundError("CSRF токен не найден в HTML")
            
            token = match.group(1)
            logger.debug(f"CSRF токен успешно получен: {token[:10]}...")
            return token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при получении токена: {e}")
            raise NetworkError("Ошибка сети при получении токена") from e
        except TokenNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении токена: {e}")
            raise
    
    def get_contester_info(self, token_csrf, wsdcid):
        """
        Получение информации о танцоре
        
        Args:
            token_csrf (str): CSRF токен
            wsdcid (int): ID танцора WSDC
            
        Returns:
            dict: Информация о танцоре
            
        Raises:
            DancerNotFoundError: Если танцор не найден
        """
        try:
            if not token_csrf:
                raise ValidationError("CSRF токен не может быть пустым")
            
            if not isinstance(wsdcid, int) or wsdcid <= 0:
                raise ValidationError(f"Неверный WSDC ID: {wsdcid}")
            
            payload = {
                'num': wsdcid,
                '_token': token_csrf
            }
            
            response = self.session.post(
                self.config.LOOKUP_URL,
                data=payload,
                headers=self.config.CONTESTER_HEADERS,
                verify=self.config.VERIFY_SSL,
                timeout=self.config.TIMEOUT
            )
            response.raise_for_status()
            
            data = response.json()
            if not data:
                raise DancerNotFoundError(f"Танцор с ID {wsdcid} не найден")
            
            logger.info(f"Информация о танцоре {wsdcid} успешно получена")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при получении информации о танцоре {wsdcid}: {e}")
            raise NetworkError(f"Ошибка сети при получении информации о танцоре {wsdcid}") from e
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON для танцора {wsdcid}: {e}")
            raise ValidationError(f"Ошибка парсинга JSON для танцора {wsdcid}") from e
        except DancerNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении информации о танцоре {wsdcid}: {e}")
            raise
    
    def selenium_lookup(self, dancer_id):
        """
        Поиск танцора через Selenium (для случаев когда API не работает)
        
        Args:
            dancer_id (int): ID танцора
            
        Returns:
            bool: True если танцор найден, False в противном случае
        """
        try:
            if not self.driver:
                raise RuntimeError("Веб-драйвер не инициализирован")
            
            self.driver.get(self.config.LOOKUP_URL)
            
            # Ожидание появления поля ввода
            input_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "q"))
            )
            input_field.clear()
            input_field.send_keys(str(dancer_id))
            
            # Отправка формы
            form = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "lookup_form"))
            )
            form.submit()
            
            # Ожидание результатов
            WebDriverWait(self.driver, 10).until(
                EC.text_to_be_present_in_element((By.ID, 'lookup_results'), str(dancer_id))
            )
            
            logger.info(f"Танцор {dancer_id} найден через Selenium")
            return True
            
        except TimeoutException:
            logger.warning(f"Таймаут при поиске танцора {dancer_id} через Selenium")
            return False
        except Exception as e:
            logger.error(f"Ошибка при поиске танцора {dancer_id} через Selenium: {e}")
            return False
    
    def process_dancers_batch(self, start_id, max_attempts=None):
        """
        Обработка группы танцоров
        
        Args:
            start_id (int): Начальный ID танцора
            max_attempts (int): Максимальное количество неудачных попыток
            
        Returns:
            list: Список обработанных танцоров
        """
        if max_attempts is None:
            max_attempts = self.config.MAX_ATTEMPTS
        
        attempts = 0
        dancer_id = start_id
        processed_dancers = []
        
        logger.info(f"Начинаем обработку танцоров с ID {start_id}")
        
        while attempts < max_attempts:
            try:
                # Проверяем существование танцора
                if self.check_id(dancer_id):
                    # Получаем токен (обновляем каждые 2 минуты)
                    if not hasattr(self, '_token_time') or \
                       time.time() - getattr(self, '_token_time', 0) > 120:
                        token = self.get_token()
                        self._token = token
                        self._token_time = time.time()
                    
                    # Получаем информацию о танцоре
                    dancer_info = self.get_contester_info(self._token, dancer_id)
                    processed_dancers.append(dancer_info)
                    
                    logger.info(f"[OK] wsdcid={dancer_id} обработан")
                    attempts = 0  # Сбрасываем счетчик неудач
                else:
                    logger.info(f"[Пропущен] wsdcid={dancer_id} не найден")
                    attempts += 1
                
                dancer_id += 1
                
                # Пауза между запросами
                if len(processed_dancers) % 10 == 0:
                    time.sleep(0.3)  # Пауза каждые 10 запросов
                
            except Exception as e:
                logger.error(f"Ошибка при обработке танцора {dancer_id}: {e}")
                attempts += 1
                time.sleep(2)  # Пауза при ошибке
        
        logger.info(f"Обработка завершена. Обработано танцоров: {len(processed_dancers)}")
        return processed_dancers
    
    def process_role_data(self, dancer_data_list):
        """
        Обработка данных о ролях танцоров
        
        Args:
            dancer_data_list (list): Список данных танцоров
            
        Returns:
            pd.DataFrame: DataFrame с обработанными данными о ролях
        """
        try:
            role_data = []
            
            for dancer_data in dancer_data_list:
                try:
                    processed_role = self.role_extractor.extract_role_info(dancer_data)
                    role_data.append(processed_role)
                except ValidationError as e:
                    logger.warning(f"Ошибка валидации данных танцора: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Ошибка обработки роли танцора: {e}")
                    continue
            
            df = pd.DataFrame(role_data)
            logger.info(f"Обработано {len(df)} записей о ролях танцоров")
            return df
            
        except Exception as e:
            logger.error(f"Ошибка при обработке данных о ролях: {e}")
            return pd.DataFrame()
    
    def process_location_data(self, df):
        """
        Обработка географических данных
        
        Args:
            df (pd.DataFrame): DataFrame с данными о локациях
            
        Returns:
            pd.DataFrame: DataFrame с обработанными географическими данными
        """
        try:
            if 'event_location' in df.columns:
                df['event_state'] = df['event_location'].apply(self.location_extractor.extract_state)
                df['event_country'] = df['event_location'].apply(self.location_extractor.extract_country)
                df['event_city'] = df['event_location'].apply(self.location_extractor.extract_city)
                
                logger.info("Географические данные успешно обработаны")
            
            return df
            
        except Exception as e:
            logger.error(f"Ошибка при обработке географических данных: {e}")
            return df
    
    def process_date_data(self, df):
        """
        Обработка данных о датах
        
        Args:
            df (pd.DataFrame): DataFrame с данными о датах
            
        Returns:
            pd.DataFrame: DataFrame с обработанными данными о датах
        """
        try:
            if 'event_date' in df.columns:
                df['event_month'] = df['event_date'].apply(self.date_extractor.extract_month)
                df['event_year'] = df['event_date'].apply(self.date_extractor.extract_year)
                
                logger.info("Данные о датах успешно обработаны")
            
            return df
            
        except Exception as e:
            logger.error(f"Ошибка при обработке данных о датах: {e}")
            return df
    
    def analyze_transitions(self, role_df):
        """
        Анализ переходов между дивизионами
        
        Args:
            role_df (pd.DataFrame): DataFrame с данными о ролях
            
        Returns:
            pd.DataFrame: DataFrame с анализом переходов
        """
        try:
            transitions_df = self.transition_analyzer.analyze_transitions(role_df)
            return transitions_df
            
        except Exception as e:
            logger.error(f"Ошибка при анализе переходов: {e}")
            return pd.DataFrame()
    
    def analyze_data(self, df):
        """
        Комплексный анализ данных
        
        Args:
            df (pd.DataFrame): DataFrame для анализа
            
        Returns:
            dict: Результаты анализа
        """
        try:
            logger.info("Начинаем комплексный анализ данных")
            
            analysis_results = {}
            
            # Анализ распределения танцоров
            if 'dominate_role' in df.columns:
                division_stats = self.data_analyzer.analyze_dancer_distribution(df)
                analysis_results['division_analysis'] = division_stats
                logger.info("Анализ распределения по дивизионам завершен")
            
            # Географический анализ
            geo_stats = self.data_analyzer.analyze_geographic_distribution(df)
            if geo_stats:
                analysis_results['geographic_analysis'] = geo_stats
                logger.info("Географический анализ завершен")
            
            # Временной анализ
            temporal_stats = self.data_analyzer.analyze_temporal_trends(df)
            if temporal_stats:
                analysis_results['temporal_analysis'] = temporal_stats
                logger.info("Временной анализ завершен")
            
            # Анализ производительности
            performance_stats = self.data_analyzer.analyze_performance_metrics(df)
            if performance_stats:
                analysis_results['performance_analysis'] = performance_stats
                logger.info("Анализ производительности завершен")
            
            logger.info("Комплексный анализ данных завершен")
            return analysis_results
            
        except Exception as e:
            logger.error(f"Ошибка при анализе данных: {e}")
            return {}
    
    def create_visualizations(self, df, output_dir=None):
        """
        Создание визуализаций
        
        Args:
            df (pd.DataFrame): DataFrame для визуализации
            output_dir (str, optional): Директория для сохранения
            
        Returns:
            dict: Пути к созданным файлам
        """
        try:
            if output_dir is None:
                output_dir = 'visualizations'
            
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            visualization_files = {}
            
            # График распределения по дивизионам
            if 'dominate_role' in df.columns:
                division_chart_path = os.path.join(output_dir, f"division_distribution_{timestamp}.png")
                self.data_visualizer.create_division_distribution_chart(df, division_chart_path)
                visualization_files['division_chart'] = division_chart_path
                logger.info("График распределения по дивизионам создан")
            
            # Временной анализ
            if 'event_year' in df.columns or 'event_month' in df.columns:
                temporal_chart_path = os.path.join(output_dir, f"temporal_analysis_{timestamp}.png")
                self.data_visualizer.create_temporal_analysis_chart(df, temporal_chart_path)
                visualization_files['temporal_chart'] = temporal_chart_path
                logger.info("График временного анализа создан")
            
            # Анализ производительности
            if 'event_points' in df.columns:
                performance_chart_path = os.path.join(output_dir, f"performance_analysis_{timestamp}.png")
                self.data_visualizer.create_performance_analysis_chart(df, performance_chart_path)
                visualization_files['performance_chart'] = performance_chart_path
                logger.info("График анализа производительности создан")
            
            # Интерактивная панель
            dashboard_path = os.path.join(output_dir, f"interactive_dashboard_{timestamp}.html")
            self.data_visualizer.create_interactive_dashboard(df, dashboard_path)
            visualization_files['dashboard'] = dashboard_path
            logger.info("Интерактивная панель создана")
            
            return visualization_files
            
        except Exception as e:
            logger.error(f"Ошибка при создании визуализаций: {e}")
            return {}
    
    def generate_report(self, df, output_dir=None):
        """
        Генерация комплексного отчета
        
        Args:
            df (pd.DataFrame): DataFrame для отчета
            output_dir (str, optional): Директория для сохранения
            
        Returns:
            str: Путь к созданному отчету
        """
        try:
            logger.info("Начинаем генерацию комплексного отчета")
            
            report_path = self.report_generator.generate_comprehensive_report(df, output_dir)
            
            if report_path:
                logger.info(f"Комплексный отчет сохранен: {report_path}")
            else:
                logger.warning("Не удалось создать отчет")
            
            return report_path
            
        except Exception as e:
            logger.error(f"Ошибка при генерации отчета: {e}")
            return ""
    
    def save_results(self, data, filename, file_type='json'):
        """
        Сохранение результатов в файл
        
        Args:
            data: Данные для сохранения
            filename (str): Имя файла
            file_type (str): Тип файла ('json', 'csv', 'excel')
        """
        try:
            if file_type == 'json':
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            elif file_type == 'csv':
                if isinstance(data, pd.DataFrame):
                    data.to_csv(filename, index=False, encoding='utf-8')
                else:
                    logger.error("Для сохранения в CSV данные должны быть DataFrame")
                    return
            elif file_type == 'excel':
                if isinstance(data, pd.DataFrame):
                    data.to_excel(filename, index=False)
                else:
                    logger.error("Для сохранения в Excel данные должны быть DataFrame")
                    return
            
            logger.info(f"Результаты сохранены в {filename}")
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении результатов в {filename}: {e}")
    
    def cleanup(self):
        """Очистка ресурсов"""
        try:
            if self.driver:
                self.driver.quit()
                logger.info("Веб-драйвер Chrome закрыт")
            
            if self.session:
                self.session.close()
                logger.info("HTTP сессия закрыта")
                
        except Exception as e:
            logger.error(f"Ошибка при очистке ресурсов: {e}")
    
    def __enter__(self):
        """Контекстный менеджер - вход"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер - выход"""
        self.cleanup()


def main():
    """Основная функция для демонстрации работы парсера"""
    try:
        with WSDCParser() as parser:
            # Обрабатываем группу танцоров
            dancers = parser.process_dancers_batch(
                start_id=Config.START_DANCER_ID,
                max_attempts=Config.MAX_ATTEMPTS
            )
            
            if dancers:
                # Сохраняем сырые данные
                parser.save_results(dancers, "raw_dancers_data.json", "json")
                
                # Обрабатываем данные о ролях
                role_df = parser.process_role_data(dancers)
                if not role_df.empty:
                    parser.save_results(role_df, "dancer_roles.csv", "csv")
                
                # Обрабатываем результаты (если есть)
                results_df = None
                if any('events' in dancer for dancer in dancers):
                    results_df = parser.results_extractor.extract_dancer_results(dancers)
                    if not results_df.empty:
                        # Обрабатываем географические данные
                        results_df = parser.process_location_data(results_df)
                        # Обрабатываем данные о датах
                        results_df = parser.process_date_data(results_df)
                        parser.save_results(results_df, "dancer_results.csv", "csv")
                
                # Анализируем переходы
                if not role_df.empty:
                    transitions_df = parser.analyze_transitions(role_df)
                    if not transitions_df.empty:
                        parser.save_results(transitions_df, "dancer_transitions.csv", "csv")
                
                # Комплексный анализ данных
                if not role_df.empty:
                    analysis_results = parser.analyze_data(role_df)
                    if analysis_results:
                        parser.save_results(analysis_results, "analysis_results.json", "json")
                
                # Создание визуализаций
                if not role_df.empty:
                    visualization_files = parser.create_visualizations(role_df)
                    if visualization_files:
                        logger.info(f"Создано {len(visualization_files)} визуализаций")
                
                # Генерация отчета
                if not role_df.empty:
                    report_path = parser.generate_report(role_df)
                    if report_path:
                        logger.info(f"Отчет создан: {report_path}")
                
                logger.info("Все данные успешно обработаны и сохранены")
            
    except Exception as e:
        logger.error(f"Критическая ошибка в main: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()

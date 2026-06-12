"""
Data Analytics Module
Модуль для анализа данных и визуализации WSDC
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Optional, Any, Tuple
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from folium import plugins
import googlemaps
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import warnings
from datetime import datetime, timedelta
import json
import os

from .logger import logger
from .exceptions import ValidationError, NetworkError
from .config import Config


class DataAnalyzer:
    """Класс для анализа данных WSDC"""
    
    def __init__(self):
        """Инициализация анализатора данных"""
        self.config = Config()
        self.gmaps = None
        self.geolocator = None
        self.setup_geocoding()
        
        # Настройка стилей для графиков
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
        
        # Игнорирование предупреждений
        warnings.filterwarnings('ignore')
    
    def setup_geocoding(self):
        """Настройка геокодинга"""
        try:
            # Google Maps API (если доступен)
            api_key = os.getenv('GOOGLE_MAPS_API_KEY')
            if api_key:
                self.gmaps = googlemaps.Client(key=api_key)
                logger.info("Google Maps API настроен")
            
            # Nominatim как резервный вариант
            self.geolocator = Nominatim(user_agent="wsdc_parser")
            logger.info("Nominatim геокодер настроен")
            
        except Exception as e:
            logger.warning(f"Ошибка при настройке геокодинга: {e}")
    
    def get_coordinates(self, location: str) -> Optional[Dict[str, float]]:
        """
        Получение координат по названию локации
        
        Args:
            location (str): Название локации
            
        Returns:
            dict or None: Словарь с координатами или None
        """
        try:
            if not location or not isinstance(location, str):
                return None
            
            # Сначала пробуем Google Maps API
            if self.gmaps:
                try:
                    geocode_result = self.gmaps.geocode(location)
                    if geocode_result:
                        lat = geocode_result[0]['geometry']['location']['lat']
                        lng = geocode_result[0]['geometry']['location']['lng']
                        return {'latitude': lat, 'longitude': lng}
                except Exception as e:
                    logger.debug(f"Google Maps API ошибка для {location}: {e}")
            
            # Резервный вариант - Nominatim
            if self.geolocator:
                try:
                    location_data = self.geolocator.geocode(location, timeout=10)
                    if location_data:
                        return {
                            'latitude': location_data.latitude,
                            'longitude': location_data.longitude
                        }
                except (GeocoderTimedOut, GeocoderUnavailable) as e:
                    logger.debug(f"Nominatim ошибка для {location}: {e}")
            
            return None
            
        except Exception as e:
            logger.warning(f"Ошибка при получении координат для {location}: {e}")
            return None
    
    def analyze_dancer_distribution(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Анализ распределения танцоров по дивизионам
        
        Args:
            df (pd.DataFrame): DataFrame с данными танцоров
            
        Returns:
            dict: Статистика распределения
        """
        try:
            if df.empty or 'dominate_role' not in df.columns:
                raise ValidationError("DataFrame пуст или не содержит колонку 'dominate_role'")
            
            # Подсчет танцоров по дивизионам
            division_counts = df['dominate_role'].value_counts()
            
            # Процентное распределение
            division_percentages = (division_counts / len(df) * 100).round(2)
            
            # Статистика
            stats = {
                'total_dancers': len(df),
                'unique_divisions': len(division_counts),
                'division_counts': division_counts.to_dict(),
                'division_percentages': division_percentages.to_dict(),
                'most_common_division': division_counts.index[0],
                'least_common_division': division_counts.index[-1]
            }
            
            logger.info(f"Проанализировано распределение {len(df)} танцоров по {len(division_counts)} дивизионам")
            return stats
            
        except Exception as e:
            logger.error(f"Ошибка при анализе распределения танцоров: {e}")
            return {}
    
    def analyze_geographic_distribution(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Анализ географического распределения
        
        Args:
            df (pd.DataFrame): DataFrame с данными о локациях
            
        Returns:
            dict: Статистика географического распределения
        """
        try:
            if df.empty:
                raise ValidationError("DataFrame пуст")
            
            stats = {}
            
            # Анализ по странам
            if 'event_country' in df.columns:
                country_counts = df['event_country'].value_counts()
                stats['country_distribution'] = {
                    'total_countries': len(country_counts),
                    'top_countries': country_counts.head(10).to_dict(),
                    'most_active_country': country_counts.index[0]
                }
            
            # Анализ по штатам (для США)
            if 'event_state' in df.columns:
                state_counts = df['event_state'].value_counts()
                stats['state_distribution'] = {
                    'total_states': len(state_counts),
                    'top_states': state_counts.head(10).to_dict(),
                    'most_active_state': state_counts.index[0] if len(state_counts) > 0 else None
                }
            
            # Анализ по городам
            if 'event_city' in df.columns:
                city_counts = df['event_city'].value_counts()
                stats['city_distribution'] = {
                    'total_cities': len(city_counts),
                    'top_cities': city_counts.head(10).to_dict(),
                    'most_active_city': city_counts.index[0] if len(city_counts) > 0 else None
                }
            
            logger.info("Географическое распределение проанализировано")
            return stats
            
        except Exception as e:
            logger.error(f"Ошибка при анализе географического распределения: {e}")
            return {}
    
    def analyze_temporal_trends(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Анализ временных трендов
        
        Args:
            df (pd.DataFrame): DataFrame с данными о датах
            
        Returns:
            dict: Статистика временных трендов
        """
        try:
            if df.empty:
                raise ValidationError("DataFrame пуст")
            
            stats = {}
            
            # Анализ по годам
            if 'event_year' in df.columns:
                year_counts = df['event_year'].value_counts().sort_index()
                stats['yearly_trends'] = {
                    'year_range': f"{year_counts.index.min()} - {year_counts.index.max()}",
                    'most_active_year': year_counts.idxmax(),
                    'yearly_counts': year_counts.to_dict()
                }
            
            # Анализ по месяцам
            if 'event_month' in df.columns:
                month_counts = df['event_month'].value_counts()
                stats['monthly_trends'] = {
                    'most_active_month': month_counts.index[0],
                    'monthly_counts': month_counts.to_dict()
                }
            
            logger.info("Временные тренды проанализированы")
            return stats
            
        except Exception as e:
            logger.error(f"Ошибка при анализе временных трендов: {e}")
            return {}
    
    def analyze_performance_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Анализ метрик производительности
        
        Args:
            df (pd.DataFrame): DataFrame с результатами соревнований
            
        Returns:
            dict: Статистика производительности
        """
        try:
            if df.empty:
                raise ValidationError("DataFrame пуст")
            
            stats = {}
            
            # Анализ очков
            if 'event_points' in df.columns:
                points_stats = df['event_points'].describe()
                stats['points_analysis'] = {
                    'mean_points': points_stats['mean'],
                    'median_points': points_stats['50%'],
                    'max_points': points_stats['max'],
                    'min_points': points_stats['min'],
                    'std_points': points_stats['std']
                }
            
            # Анализ результатов
            if 'event_result' in df.columns:
                result_counts = df['event_result'].value_counts()
                stats['result_analysis'] = {
                    'total_results': len(result_counts),
                    'top_results': result_counts.head(10).to_dict(),
                    'most_common_result': result_counts.index[0]
                }
            
            logger.info("Метрики производительности проанализированы")
            return stats
            
        except Exception as e:
            logger.error(f"Ошибка при анализе метрик производительности: {e}")
            return {}


class DataVisualizer:
    """Класс для визуализации данных WSDC"""
    
    def __init__(self):
        """Инициализация визуализатора"""
        self.analyzer = DataAnalyzer()
        
        # Настройка стилей
        plt.rcParams['figure.figsize'] = (12, 8)
        plt.rcParams['font.size'] = 10
        
        # Создание директории для графиков
        self.output_dir = 'visualizations'
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    def create_division_distribution_chart(self, df: pd.DataFrame, save_path: Optional[str] = None) -> plt.Figure:
        """
        Создание графика распределения по дивизионам
        
        Args:
            df (pd.DataFrame): DataFrame с данными танцоров
            save_path (str, optional): Путь для сохранения
            
        Returns:
            plt.Figure: Объект графика
        """
        try:
            if df.empty or 'dominate_role' not in df.columns:
                raise ValidationError("Нет данных для визуализации")
            
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
            
            # Столбчатая диаграмма
            division_counts = df['dominate_role'].value_counts()
            division_counts.plot(kind='bar', ax=ax1, color='skyblue', edgecolor='black')
            ax1.set_title('Распределение танцоров по дивизионам', fontsize=14, fontweight='bold')
            ax1.set_xlabel('Дивизион')
            ax1.set_ylabel('Количество танцоров')
            ax1.tick_params(axis='x', rotation=45)
            
            # Круговая диаграмма
            ax2.pie(division_counts.values, labels=division_counts.index, autopct='%1.1f%%', startangle=90)
            ax2.set_title('Процентное распределение по дивизионам', fontsize=14, fontweight='bold')
            
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"График сохранен в {save_path}")
            
            return fig
            
        except Exception as e:
            logger.error(f"Ошибка при создании графика распределения: {e}")
            return None
    
    def create_geographic_map(self, df: pd.DataFrame, save_path: Optional[str] = None) -> folium.Map:
        """
        Создание интерактивной карты
        
        Args:
            df (pd.DataFrame): DataFrame с географическими данными
            save_path (str, optional): Путь для сохранения
            
        Returns:
            folium.Map: Интерактивная карта
        """
        try:
            if df.empty or 'event_location' not in df.columns:
                raise ValidationError("Нет географических данных для визуализации")
            
            # Создание карты
            m = folium.Map(location=[39.8283, -98.5795], zoom_start=4)  # Центр США
            
            # Группировка по локациям
            location_counts = df['event_location'].value_counts()
            
            for location, count in location_counts.head(20).items():  # Топ 20 локаций
                coords = self.analyzer.get_coordinates(location)
                if coords:
                    folium.CircleMarker(
                        location=[coords['latitude'], coords['longitude']],
                        radius=min(count / 10, 20),  # Размер круга зависит от количества событий
                        popup=f"{location}<br>Событий: {count}",
                        color='red',
                        fill=True,
                        fillColor='red',
                        fillOpacity=0.6
                    ).add_to(m)
            
            # Добавление слоя с кластерами
            marker_cluster = plugins.MarkerCluster().add_to(m)
            
            if save_path:
                m.save(save_path)
                logger.info(f"Карта сохранена в {save_path}")
            
            return m
            
        except Exception as e:
            logger.error(f"Ошибка при создании карты: {e}")
            return None
    
    def create_temporal_analysis_chart(self, df: pd.DataFrame, save_path: Optional[str] = None) -> plt.Figure:
        """
        Создание графика временного анализа
        
        Args:
            df (pd.DataFrame): DataFrame с временными данными
            save_path (str, optional): Путь для сохранения
            
        Returns:
            plt.Figure: Объект графика
        """
        try:
            if df.empty:
                raise ValidationError("Нет данных для временного анализа")
            
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
            
            # График по годам
            if 'event_year' in df.columns:
                year_counts = df['event_year'].value_counts().sort_index()
                year_counts.plot(kind='line', ax=ax1, marker='o', linewidth=2, markersize=6)
                ax1.set_title('Активность по годам', fontsize=12, fontweight='bold')
                ax1.set_xlabel('Год')
                ax1.set_ylabel('Количество событий')
                ax1.grid(True, alpha=0.3)
            
            # График по месяцам
            if 'event_month' in df.columns:
                month_counts = df['event_month'].value_counts()
                month_counts.plot(kind='bar', ax=ax2, color='lightcoral')
                ax2.set_title('Активность по месяцам', fontsize=12, fontweight='bold')
                ax2.set_xlabel('Месяц')
                ax2.set_ylabel('Количество событий')
                ax2.tick_params(axis='x', rotation=45)
            
            # Тепловая карта активности
            if 'event_year' in df.columns and 'event_month' in df.columns:
                pivot_table = df.groupby(['event_year', 'event_month']).size().unstack(fill_value=0)
                sns.heatmap(pivot_table, annot=True, fmt='d', cmap='YlOrRd', ax=ax3)
                ax3.set_title('Тепловая карта активности', fontsize=12, fontweight='bold')
            
            # Распределение по дням недели (если есть данные)
            if 'event_date' in df.columns:
                try:
                    df['day_of_week'] = pd.to_datetime(df['event_date']).dt.day_name()
                    day_counts = df['day_of_week'].value_counts()
                    day_counts.plot(kind='pie', ax=ax4, autopct='%1.1f%%')
                    ax4.set_title('Распределение по дням недели', fontsize=12, fontweight='bold')
                except:
                    ax4.text(0.5, 0.5, 'Нет данных о днях недели', ha='center', va='center', transform=ax4.transAxes)
            
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"График временного анализа сохранен в {save_path}")
            
            return fig
            
        except Exception as e:
            logger.error(f"Ошибка при создании графика временного анализа: {e}")
            return None
    
    def create_performance_analysis_chart(self, df: pd.DataFrame, save_path: Optional[str] = None) -> plt.Figure:
        """
        Создание графика анализа производительности
        
        Args:
            df (pd.DataFrame): DataFrame с данными о производительности
            save_path (str, optional): Путь для сохранения
            
        Returns:
            plt.Figure: Объект графика
        """
        try:
            if df.empty:
                raise ValidationError("Нет данных о производительности")
            
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
            
            # Распределение очков
            if 'event_points' in df.columns:
                df['event_points'].hist(bins=30, ax=ax1, color='lightblue', edgecolor='black', alpha=0.7)
                ax1.set_title('Распределение очков', fontsize=12, fontweight='bold')
                ax1.set_xlabel('Очки')
                ax1.set_ylabel('Частота')
                ax1.grid(True, alpha=0.3)
            
            # Box plot очков по дивизионам
            if 'event_points' in df.columns and 'dominate_role' in df.columns:
                df.boxplot(column='event_points', by='dominate_role', ax=ax2)
                ax2.set_title('Распределение очков по дивизионам', fontsize=12, fontweight='bold')
                ax2.set_xlabel('Дивизион')
                ax2.set_ylabel('Очки')
                ax2.tick_params(axis='x', rotation=45)
            
            # Топ результатов
            if 'event_result' in df.columns:
                result_counts = df['event_result'].value_counts().head(10)
                result_counts.plot(kind='barh', ax=ax3, color='lightgreen')
                ax3.set_title('Топ 10 результатов', fontsize=12, fontweight='bold')
                ax3.set_xlabel('Количество')
            
            # Scatter plot очков vs места
            if 'event_points' in df.columns and 'event_result' in df.columns:
                try:
                    # Извлечение числового места из результата
                    df['place'] = df['event_result'].str.extract(r'(\d+)').astype(float)
                    ax4.scatter(df['place'], df['event_points'], alpha=0.6, color='orange')
                    ax4.set_title('Очки vs Место', fontsize=12, fontweight='bold')
                    ax4.set_xlabel('Место')
                    ax4.set_ylabel('Очки')
                    ax4.grid(True, alpha=0.3)
                except:
                    ax4.text(0.5, 0.5, 'Нет данных о местах', ha='center', va='center', transform=ax4.transAxes)
            
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"График анализа производительности сохранен в {save_path}")
            
            return fig
            
        except Exception as e:
            logger.error(f"Ошибка при создании графика анализа производительности: {e}")
            return None
    
    def create_interactive_dashboard(self, df: pd.DataFrame, save_path: Optional[str] = None) -> go.Figure:
        """
        Создание интерактивной панели с Plotly
        
        Args:
            df (pd.DataFrame): DataFrame с данными
            save_path (str, optional): Путь для сохранения
            
        Returns:
            go.Figure: Интерактивная панель
        """
        try:
            if df.empty:
                raise ValidationError("Нет данных для панели")
            
            # Создание подграфиков
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=('Распределение по дивизионам', 'Географическое распределение', 
                              'Временные тренды', 'Анализ производительности'),
                specs=[[{"type": "pie"}, {"type": "scattergeo"}],
                       [{"type": "bar"}, {"type": "histogram"}]]
            )
            
            # График 1: Распределение по дивизионам
            if 'dominate_role' in df.columns:
                division_counts = df['dominate_role'].value_counts()
                fig.add_trace(
                    go.Pie(labels=division_counts.index, values=division_counts.values, name="Дивизионы"),
                    row=1, col=1
                )
            
            # График 2: Географическое распределение (заглушка)
            fig.add_trace(
                go.Scattergeo(lat=[], lon=[], mode='markers', name="Локации"),
                row=1, col=2
            )
            
            # График 3: Временные тренды
            if 'event_year' in df.columns:
                year_counts = df['event_year'].value_counts().sort_index()
                fig.add_trace(
                    go.Bar(x=year_counts.index, y=year_counts.values, name="По годам"),
                    row=2, col=1
                )
            
            # График 4: Анализ производительности
            if 'event_points' in df.columns:
                fig.add_trace(
                    go.Histogram(x=df['event_points'], name="Очки"),
                    row=2, col=2
                )
            
            fig.update_layout(height=800, title_text="WSDC Data Dashboard")
            
            if save_path:
                fig.write_html(save_path)
                logger.info(f"Интерактивная панель сохранена в {save_path}")
            
            return fig
            
        except Exception as e:
            logger.error(f"Ошибка при создании интерактивной панели: {e}")
            return None


class ReportGenerator:
    """Класс для генерации отчетов"""
    
    def __init__(self):
        """Инициализация генератора отчетов"""
        self.analyzer = DataAnalyzer()
        self.visualizer = DataVisualizer()
        self.reports_dir = 'reports'
        
        if not os.path.exists(self.reports_dir):
            os.makedirs(self.reports_dir)
    
    def generate_comprehensive_report(self, df: pd.DataFrame, output_dir: Optional[str] = None) -> str:
        """
        Генерация комплексного отчета
        
        Args:
            df (pd.DataFrame): DataFrame с данными
            output_dir (str, optional): Директория для сохранения
            
        Returns:
            str: Путь к сохраненному отчету
        """
        try:
            if df.empty:
                raise ValidationError("Нет данных для отчета")
            
            if output_dir is None:
                output_dir = self.reports_dir
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = os.path.join(output_dir, f"wsdc_report_{timestamp}.html")
            
            # Анализ данных
            division_stats = self.analyzer.analyze_dancer_distribution(df)
            geo_stats = self.analyzer.analyze_geographic_distribution(df)
            temporal_stats = self.analyzer.analyze_temporal_trends(df)
            performance_stats = self.analyzer.analyze_performance_metrics(df)
            
            # Создание графиков
            division_chart = self.visualizer.create_division_distribution_chart(
                df, os.path.join(output_dir, f"division_chart_{timestamp}.png")
            )
            temporal_chart = self.visualizer.create_temporal_analysis_chart(
                df, os.path.join(output_dir, f"temporal_chart_{timestamp}.png")
            )
            performance_chart = self.visualizer.create_performance_analysis_chart(
                df, os.path.join(output_dir, f"performance_chart_{timestamp}.png")
            )
            
            # Создание HTML отчета
            html_content = self._create_html_report(
                df, division_stats, geo_stats, temporal_stats, performance_stats, timestamp
            )
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"Комплексный отчет сохранен в {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"Ошибка при генерации отчета: {e}")
            return ""
    
    def _create_html_report(self, df: pd.DataFrame, division_stats: dict, geo_stats: dict, 
                           temporal_stats: dict, performance_stats: dict, timestamp: str) -> str:
        """Создание HTML содержимого отчета"""
        
        html_template = f"""
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>WSDC Data Report - {timestamp}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }}
                .stat-card {{ background-color: #f9f9f9; padding: 10px; border-radius: 3px; }}
                .chart {{ text-align: center; margin: 20px 0; }}
                .chart img {{ max-width: 100%; height: auto; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>WSDC Data Analysis Report</h1>
                <p>Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                <p>Total records: {len(df)}</p>
            </div>
            
            <div class="section">
                <h2>Distribution Analysis</h2>
                <div class="stats">
                    <div class="stat-card">
                        <strong>Total Dancers:</strong> {division_stats.get('total_dancers', 'N/A')}
                    </div>
                    <div class="stat-card">
                        <strong>Unique Divisions:</strong> {division_stats.get('unique_divisions', 'N/A')}
                    </div>
                    <div class="stat-card">
                        <strong>Most Common:</strong> {division_stats.get('most_common_division', 'N/A')}
                    </div>
                </div>
                <div class="chart">
                    <img src="division_chart_{timestamp}.png" alt="Division Distribution">
                </div>
            </div>
            
            <div class="section">
                <h2>Geographic Analysis</h2>
                <div class="stats">
                    <div class="stat-card">
                        <strong>Countries:</strong> {geo_stats.get('country_distribution', {}).get('total_countries', 'N/A')}
                    </div>
                    <div class="stat-card">
                        <strong>States:</strong> {geo_stats.get('state_distribution', {}).get('total_states', 'N/A')}
                    </div>
                    <div class="stat-card">
                        <strong>Cities:</strong> {geo_stats.get('city_distribution', {}).get('total_cities', 'N/A')}
                    </div>
                </div>
            </div>
            
            <div class="section">
                <h2>Temporal Analysis</h2>
                <div class="chart">
                    <img src="temporal_chart_{timestamp}.png" alt="Temporal Trends">
                </div>
            </div>
            
            <div class="section">
                <h2>Performance Analysis</h2>
                <div class="chart">
                    <img src="performance_chart_{timestamp}.png" alt="Performance Metrics">
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_template


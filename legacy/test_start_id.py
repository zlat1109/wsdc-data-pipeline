#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
import os

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
                    print(f"Максимальный ID в {filename}: {max_id}")
        except Exception as e:
            print(f"Ошибка при чтении {filename}: {e}")
    
    if max_ids:
        overall_max = max(max_ids)
        print(f"Общий максимальный ID из всех источников: {overall_max}")
        return int(overall_max)
    else:
        print("Не удалось найти данные, используем ID по умолчанию")
        return 26410

if __name__ == "__main__":
    start_id = get_max_dancer_id_from_all_sources()
    print(f"\n🎯 Начальный ID для парсинга: {start_id}")
    
    # Дополнительная информация
    try:
        if os.path.exists('dancer_role_info.csv'):
            df = pd.read_csv('dancer_role_info.csv')
            print(f"📊 Всего записей: {len(df)}")
            print(f"📈 Диапазон ID: {df['dancer_id'].min()} - {df['dancer_id'].max()}")
    except Exception as e:
        print(f"⚠️ Не удалось прочитать данные: {e}")


# ============================================================================
# ЭТАП 3: УЛУЧШЕННЫЕ ФУНКЦИИ ОБРАБОТКИ ДАННЫХ
# Скопируйте эти функции в новую ячейку в вашем notebook'е
# ============================================================================

def extract_role_info(dancer_data):
    """
    Улучшенное извлечение информации о ролях танцора
    
    Args:
        dancer_data (dict): Данные танцора
        
    Returns:
        dict: Обработанные данные о роли
        
    Raises:
        ValidationError: Если данные некорректны
    """
    try:
        # Валидация входных данных
        if not dancer_data:
            logger.warning("Получены пустые данные танцора")
            return {}
        
        if not isinstance(dancer_data, dict):
            raise ValidationError("dancer_data должен быть словарем")
        
        logger.info(f"Извлечение информации о ролях для танцора ID: {dancer_data.get('id', 'неизвестно')}")
        
        # Очистка и обработка данных
        result = {
            'dancer_id': dancer_data.get('id'),
            'dancer_name': f"{dancer_data.get('dancer_first', '')} {dancer_data.get('dancer_last', '')}".strip(),
            'dominate_role': dancer_data.get('dominate_role'),
            'dominate_required': dancer_data.get('dominate_required'),
            'dominate_allowed': dancer_data.get('dominate_allowed'),
            'non_dominate_role': dancer_data.get('non_dominate_role'),
            'non_dominate_required': dancer_data.get('non_dominate_required'),
            'non_dominate_allowed': dancer_data.get('non_dominate_allowed'),
            'non_dominate_recommended': dancer_data.get('non_dominate_recommended'),
            'non_dominate_role_highest_level_points': dancer_data.get('non_dominate_role_highest_level_points'),
            'non_dominate_role_highest_level': dancer_data.get('non_dominate_role_highest_level'),
            'update_date': datetime.now().strftime("%Y-%m-%d")
        }
        
        # Валидация обязательных полей
        if not result['dancer_id']:
            logger.error(f"Отсутствует ID танцора в данных: {dancer_data}")
            return {}
        
        # Очистка имени от лишних символов
        result['dancer_name'] = re.sub(r'\s+', ' ', result['dancer_name']).strip()
        
        # Проверка корректности имени
        if not result['dancer_name'] or result['dancer_name'] == ' ':
            logger.warning(f"Пустое имя танцора для ID {result['dancer_id']}")
            result['dancer_name'] = f"Unknown_{result['dancer_id']}"
        
        logger.info(f"✅ Информация о ролях извлечена для танцора: {result['dancer_name']}")
        return result
        
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка при извлечении информации о ролях: {e}")
        return {}


def remove_duplicates_and_sort(filename):
    """
    Улучшенное удаление дубликатов и сортировка файла
    
    Args:
        filename (str): Путь к файлу
        
    Returns:
        bool: True если операция успешна
        
    Raises:
        ValidationError: При ошибках обработки файла
    """
    try:
        if not os.path.exists(filename):
            raise ValidationError(f"Файл не найден: {filename}")
        
        logger.info(f"Удаление дубликатов и сортировка файла: {filename}")
        
        # Чтение файла
        try:
            df = pd.read_csv(filename)
            original_count = len(df)
            logger.info(f"Загружено {original_count} записей из {filename}")
        except Exception as e:
            raise ValidationError(f"Ошибка чтения файла {filename}: {e}")
        
        # Удаление дубликатов
        df_cleaned = df.drop_duplicates()
        duplicates_removed = original_count - len(df_cleaned)
        
        if duplicates_removed > 0:
            logger.info(f"Удалено {duplicates_removed} дубликатов")
        else:
            logger.info("Дубликаты не найдены")
        
        # Сортировка (если есть колонка с ID)
        if 'dancer_id' in df_cleaned.columns:
            df_cleaned = df_cleaned.sort_values('dancer_id')
            logger.info("Данные отсортированы по dancer_id")
        elif 'id' in df_cleaned.columns:
            df_cleaned = df_cleaned.sort_values('id')
            logger.info("Данные отсортированы по id")
        
        # Сохранение обработанного файла
        backup_filename = f"{filename}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        df.to_csv(backup_filename, index=False)
        logger.info(f"Создан бэкап: {backup_filename}")
        
        df_cleaned.to_csv(filename, index=False)
        logger.info(f"✅ Файл {filename} обработан: {len(df_cleaned)} записей")
        
        return True
        
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка при обработке файла {filename}: {e}")
        return False


def extract_dancer_info(soup_list):
    """
    Улучшенное извлечение информации о танцоре из HTML
    
    Args:
        soup_list: Список BeautifulSoup объектов
        
    Returns:
        list: Список словарей с информацией о танцорах
        
    Raises:
        ValidationError: При ошибках парсинга
    """
    try:
        if not soup_list:
            logger.warning("Получен пустой список для парсинга")
            return []
        
        logger.info(f"Извлечение информации о танцорах из {len(soup_list)} элементов")
        
        dancers_info = []
        
        for i, soup in enumerate(soup_list):
            try:
                dancer_info = {}
                
                # Извлечение ID танцора
                dancer_id_elem = soup.find('td', string=re.compile(r'^\d+$'))
                if dancer_id_elem:
                    dancer_info['dancer_id'] = int(dancer_id_elem.get_text().strip())
                else:
                    logger.warning(f"ID танцора не найден в элементе {i}")
                    continue
                
                # Извлечение имени танцора
                name_elem = soup.find('td', string=re.compile(r'[A-Za-z]'))
                if name_elem:
                    dancer_info['dancer_name'] = name_elem.get_text().strip()
                else:
                    logger.warning(f"Имя танцора не найдено для ID {dancer_info.get('dancer_id')}")
                    dancer_info['dancer_name'] = f"Unknown_{dancer_info['dancer_id']}"
                
                # Извлечение роли
                role_elem = soup.find('td', string=re.compile(r'(Leader|Follower)', re.IGNORECASE))
                if role_elem:
                    dancer_info['role'] = role_elem.get_text().strip()
                
                # Извлечение дивизиона
                division_elem = soup.find('td', string=re.compile(r'(Newcomer|Novice|Intermediate|Advanced|All-Star|Champion|Master|Sophisticated)', re.IGNORECASE))
                if division_elem:
                    dancer_info['division'] = division_elem.get_text().strip()
                
                # Извлечение очков
                points_elem = soup.find('td', string=re.compile(r'^\d+$'))
                if points_elem and points_elem != dancer_id_elem:
                    dancer_info['points'] = int(points_elem.get_text().strip())
                
                # Валидация обязательных полей
                if 'dancer_id' in dancer_info and 'dancer_name' in dancer_info:
                    dancers_info.append(dancer_info)
                    logger.debug(f"Извлечена информация о танцоре: {dancer_info['dancer_name']} (ID: {dancer_info['dancer_id']})")
                else:
                    logger.warning(f"Неполная информация о танцоре в элементе {i}")
                
            except Exception as e:
                logger.error(f"Ошибка при обработке элемента {i}: {e}")
                continue
        
        logger.info(f"✅ Извлечена информация о {len(dancers_info)} танцорах")
        return dancers_info
        
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка при извлечении информации о танцорах: {e}")
        return []


def validate_and_clean_data(data, data_type="general"):
    """
    Валидация и очистка данных
    
    Args:
        data: Данные для валидации
        data_type (str): Тип данных ("dancer", "event", "location")
        
    Returns:
        dict: Очищенные и валидированные данные
        
    Raises:
        ValidationError: При ошибках валидации
    """
    try:
        if not data:
            raise ValidationError("Получены пустые данные")
        
        cleaned_data = {}
        
        if data_type == "dancer":
            # Валидация данных танцора
            required_fields = ['dancer_id', 'dancer_name']
            for field in required_fields:
                if field not in data or not data[field]:
                    raise ValidationError(f"Отсутствует обязательное поле: {field}")
            
            # Очистка имени
            if 'dancer_name' in data:
                cleaned_data['dancer_name'] = re.sub(r'\s+', ' ', str(data['dancer_name'])).strip()
            
            # Валидация ID
            if 'dancer_id' in data:
                try:
                    cleaned_data['dancer_id'] = int(data['dancer_id'])
                    if cleaned_data['dancer_id'] <= 0:
                        raise ValidationError("ID танцора должен быть положительным числом")
                except (ValueError, TypeError):
                    raise ValidationError("ID танцора должен быть числом")
            
        elif data_type == "event":
            # Валидация данных ивента
            if 'event_name' in data:
                cleaned_data['event_name'] = str(data['event_name']).strip()
            
            if 'location' in data:
                cleaned_data['location'] = str(data['location']).strip()
            
        elif data_type == "location":
            # Валидация данных локации
            if 'location' in data:
                location = str(data['location']).strip()
                if ',' in location:
                    cleaned_data['location'] = location
                else:
                    logger.warning(f"Некорректный формат локации: {location}")
        
        logger.info(f"✅ Данные типа '{data_type}' валидированы и очищены")
        return cleaned_data
        
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка при валидации данных типа '{data_type}': {e}")
        raise ValidationError(f"Ошибка валидации: {e}")


def safe_dataframe_operation(df, operation, *args, **kwargs):
    """
    Безопасная операция с DataFrame
    
    Args:
        df: DataFrame для обработки
        operation (str): Название операции ('drop_duplicates', 'sort_values', etc.)
        *args, **kwargs: Аргументы операции
        
    Returns:
        DataFrame: Результат операции
        
    Raises:
        ValidationError: При ошибках обработки
    """
    try:
        if df is None or df.empty:
            logger.warning("Получен пустой DataFrame")
            return df
        
        logger.info(f"Выполнение операции '{operation}' с DataFrame ({len(df)} записей)")
        
        # Выполнение операции
        if hasattr(df, operation):
            method = getattr(df, operation)
            result = method(*args, **kwargs)
            
            logger.info(f"✅ Операция '{operation}' выполнена успешно")
            return result
        else:
            raise ValidationError(f"Операция '{operation}' не поддерживается для DataFrame")
        
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Ошибка при выполнении операции '{operation}': {e}")
        raise ValidationError(f"Ошибка обработки DataFrame: {e}")


print("✅ Улучшенные функции обработки данных готовы!")
print("🔧 Добавлена валидация и очистка данных")
print("📝 Подробное логирование операций")
print("🛡️ Безопасная обработка ошибок")
print("📊 Улучшенная работа с DataFrame")


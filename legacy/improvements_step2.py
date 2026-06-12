# ============================================================================
# ЭТАП 2: УЛУЧШЕННЫЕ ФУНКЦИИ API
# Скопируйте эти функции в новую ячейку в вашем notebook'е
# ============================================================================

def check_id(session, dancer_id):
    """
    Проверка существования танцора по ID с улучшенной обработкой ошибок
    
    Args:
        session: HTTP сессия
        dancer_id (int): ID танцора для проверки
        
    Returns:
        bool: True если танцор существует, False если нет
        
    Raises:
        NetworkError: При сетевых ошибках
        ValidationError: При некорректных данных
    """
    try:
        # Валидация входных данных
        if not isinstance(dancer_id, int) or dancer_id <= 0:
            raise ValidationError(f"Некорректный ID танцора: {dancer_id}")
        
        logger.info(f"Проверка существования танцора ID: {dancer_id}")
        
        # Формирование URL
        url = f"{config.CHECK_CONTESTERS_URL}{dancer_id}"
        
        # Выполнение запроса с повторными попытками
        for attempt in range(config.MAX_RETRIES):
            try:
                response = session.get(
                    url, 
                    headers=config.CHECK_CONTESTERS_HEADERS,
                    timeout=config.TIMEOUT,
                    verify=config.VERIFY_SSL
                )
                response.raise_for_status()
                
                # Проверка ответа
                if response.status_code == 200:
                    data = response.json()
                    exists = len(data) > 0
                    
                    if exists:
                        logger.info(f"✅ Танцор ID {dancer_id} найден")
                    else:
                        logger.info(f"❌ Танцор ID {dancer_id} не найден")
                    
                    return exists
                else:
                    logger.warning(f"Неожиданный статус код: {response.status_code}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Таймаут при попытке {attempt + 1}/{config.MAX_RETRIES} для ID {dancer_id}")
                if attempt == config.MAX_RETRIES - 1:
                    raise NetworkError(f"Таймаут при проверке танцора ID {dancer_id}")
                time.sleep(1)  # Пауза перед повторной попыткой
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Ошибка сети при проверке танцора ID {dancer_id}: {e}")
                if attempt == config.MAX_RETRIES - 1:
                    raise NetworkError(f"Сетевая ошибка при проверке танцора ID {dancer_id}: {e}")
                time.sleep(1)
        
        return False
        
    except (ValidationError, NetworkError):
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка при проверке танцора ID {dancer_id}: {e}")
        raise ValidationError(f"Ошибка при проверке танцора ID {dancer_id}: {e}")


def get_token(session):
    """
    Получение CSRF токена с улучшенной обработкой ошибок
    
    Args:
        session: HTTP сессия
        
    Returns:
        str: CSRF токен
        
    Raises:
        TokenNotFoundError: Если токен не найден
        NetworkError: При сетевых ошибках
    """
    try:
        logger.info("Получение CSRF токена...")
        
        # Выполнение запроса с повторными попытками
        for attempt in range(config.MAX_RETRIES):
            try:
                response = session.get(
                    config.TOKEN_URL,
                    headers=config.TOKEN_HEADERS,
                    timeout=config.TIMEOUT,
                    verify=config.VERIFY_SSL
                )
                response.raise_for_status()
                
                # Парсинг HTML для поиска токена
                soup = BeautifulSoup(response.text, 'html.parser')
                token_input = soup.find('input', {'name': '_token'})
                
                if token_input and token_input.get('value'):
                    token = token_input['value']
                    logger.info(f"✅ CSRF токен получен: {token[:10]}...")
                    return token
                else:
                    logger.warning(f"Токен не найден в HTML (попытка {attempt + 1}/{config.MAX_RETRIES})")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Таймаут при получении токена (попытка {attempt + 1}/{config.MAX_RETRIES})")
                if attempt == config.MAX_RETRIES - 1:
                    raise NetworkError("Таймаут при получении CSRF токена")
                time.sleep(1)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Ошибка сети при получении токена: {e}")
                if attempt == config.MAX_RETRIES - 1:
                    raise NetworkError(f"Сетевая ошибка при получении токена: {e}")
                time.sleep(1)
        
        # Если токен не найден после всех попыток
        raise TokenNotFoundError("CSRF токен не найден после всех попыток")
        
    except (TokenNotFoundError, NetworkError):
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка при получении токена: {e}")
        raise TokenNotFoundError(f"Ошибка при получении токена: {e}")


def get_contester_info(session, token_csrf, dancer_id):
    """
    Получение информации о танцоре с улучшенной обработкой ошибок
    
    Args:
        session: HTTP сессия
        token_csrf (str): CSRF токен
        dancer_id (int): ID танцора
        
    Returns:
        dict: Информация о танцоре
        
    Raises:
        DancerNotFoundError: Если танцор не найден
        NetworkError: При сетевых ошибках
        ValidationError: При ошибках валидации
    """
    try:
        # Валидация входных данных
        if not token_csrf:
            raise ValidationError("CSRF токен не может быть пустым")
        if not isinstance(dancer_id, int) or dancer_id <= 0:
            raise ValidationError(f"Некорректный ID танцора: {dancer_id}")
        
        logger.info(f"Получение информации о танцоре ID: {dancer_id}")
        
        # Подготовка данных для запроса
        data = {
            '_token': token_csrf,
            'wsdcid': str(dancer_id)
        }
        
        # Выполнение запроса с повторными попытками
        for attempt in range(config.MAX_RETRIES):
            try:
                response = session.post(
                    config.LOOKUP_URL,
                    data=data,
                    headers=config.CONTESTER_HEADERS,
                    timeout=config.TIMEOUT,
                    verify=config.VERIFY_SSL
                )
                response.raise_for_status()
                
                # Проверка ответа
                if response.status_code == 200:
                    try:
                        result = response.json()
                        
                        # Проверка наличия данных
                        if result and isinstance(result, dict):
                            logger.info(f"✅ Информация о танцоре ID {dancer_id} получена")
                            return result
                        else:
                            logger.warning(f"Пустой или некорректный ответ для танцора ID {dancer_id}")
                            
                    except json.JSONDecodeError as e:
                        logger.error(f"Ошибка парсинга JSON для танцора ID {dancer_id}: {e}")
                        if attempt == config.MAX_RETRIES - 1:
                            raise ValidationError(f"Ошибка парсинга JSON для танцора ID {dancer_id}")
                        continue
                        
                else:
                    logger.warning(f"Неожиданный статус код: {response.status_code}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Таймаут при получении данных танцора ID {dancer_id} (попытка {attempt + 1}/{config.MAX_RETRIES})")
                if attempt == config.MAX_RETRIES - 1:
                    raise NetworkError(f"Таймаут при получении данных танцора ID {dancer_id}")
                time.sleep(1)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Ошибка сети при получении данных танцора ID {dancer_id}: {e}")
                if attempt == config.MAX_RETRIES - 1:
                    raise NetworkError(f"Сетевая ошибка при получении данных танцора ID {dancer_id}: {e}")
                time.sleep(1)
        
        # Если данные не получены после всех попыток
        raise DancerNotFoundError(f"Данные танцора ID {dancer_id} не получены после всех попыток")
        
    except (DancerNotFoundError, NetworkError, ValidationError):
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка при получении данных танцора ID {dancer_id}: {e}")
        raise ValidationError(f"Ошибка при получении данных танцора ID {dancer_id}: {e}")


def safe_request(session, method, url, **kwargs):
    """
    Безопасный HTTP запрос с автоматическими повторными попытками
    
    Args:
        session: HTTP сессия
        method (str): HTTP метод ('GET', 'POST', etc.)
        url (str): URL для запроса
        **kwargs: Дополнительные параметры запроса
        
    Returns:
        requests.Response: Ответ сервера
        
    Raises:
        NetworkError: При неудачных попытках
    """
    for attempt in range(config.MAX_RETRIES):
        try:
            response = session.request(
                method,
                url,
                timeout=config.TIMEOUT,
                verify=config.VERIFY_SSL,
                **kwargs
            )
            response.raise_for_status()
            return response
            
        except requests.exceptions.Timeout:
            logger.warning(f"Таймаут при запросе {method} {url} (попытка {attempt + 1}/{config.MAX_RETRIES})")
            if attempt == config.MAX_RETRIES - 1:
                raise NetworkError(f"Таймаут при запросе {method} {url}")
            time.sleep(1)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при запросе {method} {url}: {e}")
            if attempt == config.MAX_RETRIES - 1:
                raise NetworkError(f"Сетевая ошибка при запросе {method} {url}: {e}")
            time.sleep(1)
    
    raise NetworkError(f"Не удалось выполнить запрос {method} {url} после {config.MAX_RETRIES} попыток")


print("✅ Улучшенные функции API готовы!")
print("🔧 Добавлена обработка ошибок и повторные попытки")
print("📝 Подробное логирование всех операций")
print("⚡ Автоматические паузы между попытками")


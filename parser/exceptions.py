class WSDCParserError(Exception):
    """Базовое исключение для парсера WSDC"""
    pass

class TokenNotFoundError(WSDCParserError):
    """CSRF токен не найден"""
    pass

class DancerNotFoundError(WSDCParserError):
    """Танцор не найден"""
    pass

class NetworkError(WSDCParserError):
    """Ошибка сети"""
    pass

class ValidationError(WSDCParserError):
    """Ошибка валидации данных"""
    pass

class ConfigurationError(WSDCParserError):
    """Ошибка конфигурации"""
    pass


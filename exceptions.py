class MissingEnvironmentVariableError(Exception):
    """Исключение для отсутствующих переменных окружения."""
    pass


class APIRequestError(Exception):
    """Исключение для ошибок запроса к API."""
    pass


class UnknownHomeworkStatusError(Exception):
    """Исключение для неизвестного статуса домашней работы."""
    pass


class TelegramSendMessageError(Exception):
    """Исключение для ошибок отправки сообщения в Telegram."""
    pass

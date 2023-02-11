class StatusCodeError(Exception):
    """Ошибка запроса."""
    pass


class SendMessageException(Exception):
    """Ошибка отправки сообщения в telegram."""
    pass


class TokenError(Exception):
    """Ошибка в токенах."""
    pass

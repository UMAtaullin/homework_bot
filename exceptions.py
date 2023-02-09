class StatusCodeError(Exception):
    """Код запроса отличается от 200."""

    pass


class ResponseError(Exception):
    """Отказ от обслуживания."""

    pass


class TokenError(Exception):
    """Ошибка в токенах."""

    pass

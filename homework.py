import json
import logging
import os
import time
from http import HTTPStatus
from typing import Dict, List

import requests
import telegram
from dotenv import load_dotenv
from requests.exceptions import RequestException
from telegram import Bot

from exceptions import SendMessageException, StatusCodeError, TokenError

load_dotenv()

PRACTICUM_TOKEN: str = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN: str = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID: str = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD: int = 600
ONE_MONTH = 3600 * 24 * 30
ENDPOINT: str = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS: Dict[str, str] = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS: Dict[str, str] = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

TOKENS = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')

API_ANSWER_ERROR = ('Ошибка подключения к API: {error}. '
                    'endpoint: {url}, headers: {headers}, params: {params}')
STATUS_CODE_ERROR = ('Ошибка при запросе к API: '
                     'status_code: {status_code}, endpoint: {url}, '
                     'headers: {headers}, params: {params}')


def logging_setup() -> None:
    """Настраивает логи."""
    logging.basicConfig(
        format=('{asctime} - {levelname} - {name} - '
                '{filename} - {lineno} - {message}'),
        style='{',
        level=logging.DEBUG,
        encoding='UTF-8'
    )


def check_tokens() -> bool:
    """Проверка наличия токенов."""
    flag = True
    for name in TOKENS:
        if globals()[name] is None:
            logging.critical('Токен {} не найден!'.format(name))
            flag = False
    return flag


def send_message(bot: Bot, message: str) -> None:
    """Отправляет сообщение в telegram."""
    try:
        logging.debug('Попытка отправки сообщения в telegram')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info('Отправлено сообщение: "{}"'.format(message))
    except telegram.error.TelegramError as error:
        logging.error(f'Не удалось отправить сообщение в telegram: {error}')
        raise SendMessageException(logging.error)


def get_api_answer(timestamp: int) -> Dict[str, List[dict]]:
    """Отправляем запрос к API и проверяем статус кода."""
    parameters = dict(
        url=ENDPOINT,
        headers=HEADERS,
        params={'from_date': timestamp})
    try:
        response = requests.get(**parameters)
    except RequestException as error:
        raise ConnectionError(
            API_ANSWER_ERROR.format(error=error, **parameters))
    status_code = response.status_code
    if status_code != HTTPStatus.OK:
        raise StatusCodeError(
            STATUS_CODE_ERROR.format(status_code=status_code, **parameters))
    try:
        return response.json()
    except json.JSONDecodeError:
        logging.exception('Сервер вернул невалидный ответ')


def check_response(response: Dict[str, List[dict]]) -> dict:
    """Проверка ответа API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Ожидаемый тип данных — словарь!')
    if 'homeworks' not in response and 'current_date' not in response:
        raise KeyError('В ответе от API отсутствует ключ homeworks')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Ожидаемый тип данных — список!')
    return homeworks


def parse_status(homework: dict) -> str:
    """Извлечение статуса работы."""
    if 'homework_name' not in homework:
        raise KeyError('Не найден ключ homework_name!')
    if 'status' not in homework:
        raise KeyError('Не найден ключ status!')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус работы - {homework_status}')
    return ('Изменился статус проверки работы "{homework_name}". {verdict}'
            ).format(homework_name=homework_name,
                     verdict=HOMEWORK_VERDICTS.get(homework_status)
                     )


def main() -> None:
    """Основная логика работы бота."""
    if not check_tokens():
        raise TokenError('Ошибка в токенах!')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - ONE_MONTH
    start_message = 'Бот начал работу'
    send_message(bot, start_message)
    logging.info(start_message)
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                send_message(bot, parse_status(homeworks[0]))
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.exception(message)
            try:
                bot.send_message(TELEGRAM_CHAT_ID, message)
            except Exception as error:
                logging.exception(
                    'Ошибка при отправке сообщения: {}'.format(error))
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging_setup()
    logger = logging.getLogger(__name__)
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    main()

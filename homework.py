import logging
import os
import time

import requests
import telegram
from dotenv import load_dotenv
from requests.exceptions import RequestException

from exceptions import (ResponseError, StatusCodeError, TokenError)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ONE_MONTH = 3600 * 24 * 30
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

TOKENS = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')

API_ANSWER_ERROR = ('Ошибка подключения к API: {error}. '
                    'endpoint: {url}, headers: {headers}, params: {params}')
RESPONSE_ERROR = ('Отказ от обслуживания: {error}, key {key}. '
                  'endpoint: {url}, headers: {headers}, params: {params}')
STATUS_CODE_ERROR = ('Ошибка при запросе к API: '
                     'status_code: {status_code}, endpoint: {url}, '
                     'headers: {headers}, params: {params}')


def logging_setup():
    """Настраивает логи."""
    logging.basicConfig(
        format=('{asctime} - {levelname} - {name} - '
                '{filename} - {lineno} - {message}'),
        style='{',
        level=logging.DEBUG,
        encoding='UTF-8'
    )


def check_tokens():
    """Проверка наличия токенов."""
    flag = True
    for name in TOKENS:
        if globals()[name] is None:
            logging.critical('Токен {} не найден!'.format(name))
            flag = False
    return flag


def send_message(bot, message):
    """Отправляет сообщение в telegram."""
    try:
        logging.debug('Попытка отправки сообщения в telegram')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info('Отправлено сообщение: "{}"'.format(message))
    except telegram.error.TelegramError as error:
        logging.error(f'Не удалось отправить сообщение в telegram: {error}')
        raise Exception(error)


def get_api_answer(timestamp):
    """Отправляем запрос к API и проверяем статус 200."""
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
    if status_code != 200:
        raise StatusCodeError(
            STATUS_CODE_ERROR.format(status_code=status_code, **parameters))
    response_json = response.json()
    for key in ('error', 'code'):
        if key in response_json:
            raise ResponseError(
                RESPONSE_ERROR.format(
                    error=response_json[key],
                    key=key,
                    **parameters))
    return response_json


def check_response(response):
    """Проверка ответа API на корректность."""
    if type(response) is not dict:
        raise TypeError('Ответ API не является словарем')
    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ homeworks')
    homeworks = response['homeworks']
    if type(homeworks) is not list:
        raise TypeError(
            'Под ключом `homeworks` домашки приходят не в виде списка')
    return response.get('homeworks')


def parse_status(homework):
    """Извлечение статуса работы."""
    status = homework['status']
    if 'homework_name' not in homework:
        raise KeyError('Не найден ключ "homework_name"!')
    if status not in HOMEWORK_VERDICTS:
        raise ValueError('Неизвестный статус: {}'.format(status))
    return ('Изменился статус проверки работы "{}". {}'.format(
        homework['homework_name'],
        HOMEWORK_VERDICTS.get(status)))


def main():
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

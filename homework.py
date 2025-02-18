import logging
import os
import sys
import time

from dotenv import load_dotenv
import requests
from telebot import TeleBot, apihelper

from exceptions import (
    APIRequestError,
    MissingEnvironmentVariableError,
    TelegramSendMessageError,
    UnknownHomeworkStatusError
)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('./homework_log.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def get_api_answer(timestamp):
    """Делает запрос к API и возвращает ответ, преобразованный из JSON."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != 200:
            error_message = (
                f'API вернул код, отличный от 200. '
                f'Код ответа: {response.status_code}, '
                f'Причина: {response.reason}, '
                f'Текст ответа: {response.text}'
            )
            logging.error(error_message)
            raise APIRequestError(error_message)
        return response.json()
    except requests.RequestException as error:
        logging.error(f'Сбой при запросе к API: {error}')
        raise APIRequestError(f'Сбой при запросе к API: {error}')


def check_response(response):
    """Проверяет ответ API на соответствие ожидаемой структуре."""
    if not isinstance(response, dict):
        logging.error('Ответ API должен быть словарем.')
        raise TypeError('Ответ API должен быть словарем.')

    if 'homeworks' not in response:
        logging.error('В ответе API отсутствует ключ "homeworks".')
        raise KeyError('В ответе API отсутствует ключ "homeworks".')

    if not isinstance(response['homeworks'], list):
        logging.error('Значение по ключу "homeworks" должно быть списком.')
        raise TypeError('Значение по ключу "homeworks" должно быть списком.')

    if not response['homeworks']:
        logging.debug('Отсутствие в ответе новых статусов.')

    return response['homeworks']


def parse_status(homework):
    """Извлекает статус домашней работы и возвращает строку с вердиктом."""
    if 'status' not in homework:
        logging.error(
            'В информации о домашней работе отсутствует ключ "status".'
        )
        raise KeyError(
            'В информации о домашней работе отсутствует ключ "status".'
        )

    if 'homework_name' not in homework:
        logging.error(
            'В информации о домашней работе отсутствует ключ "homework_name".'
        )
        raise KeyError(
            'В информации о домашней работе отсутствует ключ "homework_name".'
        )

    status = homework['status']
    homework_name = homework['homework_name']

    if status not in HOMEWORK_VERDICTS:
        logging.error(f'Неизвестный статус домашней работы: {status}')
        raise UnknownHomeworkStatusError(
            f'Неизвестный статус домашней работы: {status}'
        )

    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Бот отправил сообщение: "{message}"')
    except apihelper.ApiException as error:
        logging.error(f'Сбой при отправке сообщения в Telegram: {error}')
        raise TelegramSendMessageError(error)


def main():
    """Основная логика работы бота."""
    try:
        if not check_tokens():
            raise MissingEnvironmentVariableError(
                'Отсутствует одна или несколько переменных окружения'
            )
    except MissingEnvironmentVariableError as error:
        logger.critical(error)
        sys.exit()

    bot = TeleBot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            else:
                logger.debug('Новые статусы в ответе отсутствуют')
            current_timestamp = response.get(
                'current_date',
                int(time.time()) - RETRY_PERIOD
            )
        except Exception as error:
            logger.error(error)
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()

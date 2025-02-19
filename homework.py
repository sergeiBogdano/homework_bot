import logging
import os
import sys
import time
from http import HTTPStatus

from dotenv import load_dotenv
import requests
from telebot import TeleBot, apihelper

from exceptions import (
    InvalidResponseCodeError,
    MissingEnvironmentVariableError,
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

log_file_path = os.path.join(os.path.expanduser('~'), 'homework_log.log')

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s'
    ' [%(levelname)s]'
    ' %(filename)s:%(lineno)d'
    ' - %(funcName)s()'
    ' - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def check_tokens():
    """Проверяет доступность переменных окружения и токенах."""
    tokens = (
        ('PRACTICUM_TOKEN', PRACTICUM_TOKEN),
        ('TELEGRAM_TOKEN', TELEGRAM_TOKEN),
        ('TELEGRAM_CHAT_ID', TELEGRAM_CHAT_ID)
    )
    missing_tokens = []
    for name, token in tokens:
        if not token:
            logger.critical(f'Отсутствует токен: {name}')
            missing_tokens.append(name)
    if missing_tokens:
        missing_tokens_str = ', '.join(missing_tokens)
        raise MissingEnvironmentVariableError(
            f'Отсутствуют следующие переменные окружения: '
            f'{missing_tokens_str}'
        )
    return True


def get_api_answer(timestamp):
    """Делает запрос к API и возвращает ответ, преобразованный из JSON."""
    request_params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}
    }

    logger.debug(
        "Начало запроса к API: "
        "URL=%(url)s,"
        " Headers=%(headers)s,"
        " Params=%(params)s",
        request_params
    )

    try:
        response = requests.get(**request_params)
    except requests.RequestException as error:
        raise ConnectionError(
            f"Сбой при запросе к API: URL={request_params['url']}, "
            f"Headers={request_params['headers']},"
            f" Params={request_params['params']}, "
            f"Ошибка: {error}"
        )
    if response.status_code != HTTPStatus.OK:
        raise InvalidResponseCodeError(
            f"API вернул код, отличный от 200: Код ответа="
            f"{response.status_code}, "
            f"Причина={response.reason}, Текст ответа={response.text}"
        )
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие ожидаемой структуре."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API должен быть словарем.')
    if 'homeworks' not in response:
        raise KeyError('В ответе API отсутствует ключ "homeworks".')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Значение по ключу "homeworks" должно быть списком.')
    return homeworks


def parse_status(homework):
    """Извлекает статус домашней работы и возвращает строку с вердиктом."""
    if 'status' not in homework:
        raise KeyError(
            'В информации о домашней работе отсутствует ключ "status".'
        )
    if 'homework_name' not in homework:
        raise KeyError(
            'В информации о домашней работе отсутствует ключ "homework_name".'
        )
    status = homework['status']
    homework_name = homework['homework_name']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус домашней работы: {status}')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат и возвращает статус отправки."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except apihelper.ApiException as error:
        logger.error(f'Сбой при отправке сообщения в Telegram: {error}')
        return False
    logger.debug(f'Бот отправил сообщение: "{message}"')
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствует одна или несколько переменных окружения')
        sys.exit()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_message = None

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)

            if not homeworks:
                logger.debug('Новые статусы в ответе отсутствуют')
                continue
            homework = homeworks[0]
            message = parse_status(homework)
            if message != last_message:
                if send_message(bot, message):
                    last_message = message
            current_timestamp = response.get(
                'current_date',
                current_timestamp
            )

        except Exception as error:
            logger.exception('Сбой в работе программы')
            message = f'Сбой в работе программы: {error}'

            if message != last_message:
                if send_message(bot, message):
                    last_message = message

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()

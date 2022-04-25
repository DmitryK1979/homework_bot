import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправляет сообщение в чат."""
    try:
        text = message
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
        logger.info('Сообщение успешно отправлено')
    except telegram.error.TelegramError:
        logger.error('Ошибка при отправке сообщения')


def get_api_answer(current_timestamp):
    """Запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=params
        )
        response = homework_statuses.json()
    except requests.RequestException as error:
        logging.error(f'Сбой при запросе к эндпоинту {error}')
    except TypeError as error:
        logging.error(f'Объект JSON не верного типа {error}')
    else:
        if homework_statuses.status_code != 200:
            raise ValueError(logging.error(
                'Код ответа сервера не соотвествует ожидаемому при запросе к'
                'эндпоинту API-сервиса'
            ))
        return(response)


def check_response(response):
    """Возвращает список домашних работ из ответа API."""
    try:
        homeworks = response['homeworks']
    except KeyError as error:
        raise KeyError(f'Отсутствуют ожидаемые ключи в ответе API: {error}')
    else:
        if not isinstance(homeworks, list):
            raise TypeError(
                logging.error('Неправильный формат списка домашних работ.'))
        if homeworks is None:
            raise Exception(
                logging.error('Нет списка домашних работ.'))
        return homeworks


def parse_status(homework):
    """Извлекает статусы домашних работ."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_name is None or homework_status is None:
        logger.error('Отсутствуют ожидаемые ключи в ответе API')
        raise KeyError('Отсутсвует один из ключей')
    if homework_status in HOMEWORK_STATUSES:
        verdict = HOMEWORK_STATUSES.get(homework_status)
    else:
        logger.error('Статус работы неизвестен')
        raise KeyError('Неизвестный статус домашней работы')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступности переменных окружения."""
    enviroment_variables = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }

    for var, token in enviroment_variables.items():
        if token is None:
            logging.critical(
                f'Отсутствует необходимая переменная окружения: {var}'
            )
            return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Недоступна одна или несколько переменных окружения.')
        sys.exit('Работа программы завершена.')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    if bot.getMe()['is_bot'] is True:
        message = ('Бот корректно инициализирован')
        logging.info(message)
    current_timestamp = int(time.time())
    last_error_message = ''
    last_homework = 0

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if homework != last_homework:
                last_homework = homework
                message = parse_status(homework[0])
                send_message(bot, message)
            current_timestamp = response.get['current_date']
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != last_error_message:
                send_message(bot, message)
                last_error_message = message
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()

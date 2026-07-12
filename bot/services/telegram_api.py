# bot/services/telegram_api.py
"""
Низкоуровневый HTTP-клиент Telegram Bot API.
Только стандартная библиотека requests — без python-telegram-bot.
Все функции синхронные.
"""
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _url(method: str) -> str:
    return f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"


# ---------------------------------------------------------------------------
# Отправка сообщений
# ---------------------------------------------------------------------------

def send_message(chat_id: int, text: str, reply_markup: dict = None, parse_mode: str = 'HTML') -> dict | None:
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode}
    if reply_markup:
        payload['reply_markup'] = reply_markup
    try:
        r = requests.post(_url('sendMessage'), json=payload, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error('send_message error chat_id=%s: %s', chat_id, e)
        return None
    
def send_document(chat_id: int, file_path: str, caption: str = '') -> dict | None:
    """
    Отправить файл (документ) пользователю через sendDocument.

    :param chat_id:   Telegram chat_id получателя
    :param file_path: абсолютный путь к файлу на диске
    :param caption:   подпись к файлу (опционально)
    """
    try:
        with open(file_path, 'rb') as f:
            files = {'document': f}
            data = {'chat_id': chat_id}
            if caption:
                data['caption'] = caption
            resp = requests.post(_url('sendDocument'), data=data, files=files, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error('send_document error chat_id=%s file=%s: %s', chat_id, file_path, e)
        return None



def answer_callback_query(callback_query_id: str, text: str = '') -> dict | None:
    try:
        r = requests.post(_url('answerCallbackQuery'),
                          json={'callback_query_id': callback_query_id, 'text': text},
                          timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error('answer_callback_query error: %s', e)
        return None


# ---------------------------------------------------------------------------
# Файлы
# ---------------------------------------------------------------------------

def get_file_info(file_id: str) -> dict | None:
    try:
        r = requests.post(_url('getFile'), json={'file_id': file_id}, timeout=10)
        r.raise_for_status()
        return r.json().get('result')
    except Exception as e:
        logger.error('get_file_info error file_id=%s: %s', file_id, e)
        return None


def download_file(file_id: str) -> bytes | None:
    info = get_file_info(file_id)
    if not info:
        return None
    file_path = info.get('file_path')
    try:
        url = f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}/{file_path}"
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        return r.content
    except Exception as e:
        logger.error('download_file error file_id=%s: %s', file_id, e)
        return None


# ---------------------------------------------------------------------------
# Вебхук
# ---------------------------------------------------------------------------

def set_webhook(webhook_url: str, secret: str = '') -> dict | None:
    payload = {
        'url': webhook_url,
        'allowed_updates': ['message', 'callback_query'],
        'drop_pending_updates': True,
    }
    if secret:
        payload['secret_token'] = secret
    try:
        r = requests.post(_url('setWebhook'), json=payload, timeout=10)
        r.raise_for_status()
        result = r.json()
        logger.info('setWebhook: %s', result)
        return result
    except Exception as e:
        logger.error('set_webhook error: %s', e)
        return None


def delete_webhook() -> dict | None:
    try:
        r = requests.post(_url('deleteWebhook'), json={'drop_pending_updates': True}, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error('delete_webhook error: %s', e)
        return None


def get_webhook_info() -> dict | None:
    try:
        r = requests.get(_url('getWebhookInfo'), timeout=10)
        r.raise_for_status()
        return r.json().get('result')
    except Exception as e:
        logger.error('get_webhook_info error: %s', e)
        return None


# ---------------------------------------------------------------------------
# Хелперы клавиатур
# ---------------------------------------------------------------------------

def inline_keyboard(rows: list[list[tuple[str, str]]]) -> dict:
    """
    rows = [
        [('Кнопка 1', 'cb_data_1'), ('Кнопка 2', 'cb_data_2')],
        [('Назад',    'back')],
    ]
    """
    return {
        'inline_keyboard': [
            [{'text': text, 'callback_data': data} for text, data in row]
            for row in rows
        ]
    }


def reply_keyboard(rows: list[list[str]], resize: bool = True, one_time: bool = False) -> dict:
    """
    rows = [['Категории', 'Контакты'], ['Задать вопрос']]
    """
    return {
        'keyboard': [[{'text': btn} for btn in row] for row in rows],
        'resize_keyboard': resize,
        'one_time_keyboard': one_time,
    }


def remove_keyboard() -> dict:
    return {'remove_keyboard': True}


# ---------------------------------------------------------------------------
# Редактирование и удаление сообщений
# ---------------------------------------------------------------------------

def edit_message_text(chat_id: int, message_id: int, text: str,
                      reply_markup: dict = None, parse_mode: str = 'HTML') -> dict | None:
    payload = {
        'chat_id':    chat_id,
        'message_id': message_id,
        'text':       text,
        'parse_mode': parse_mode,
    }
    if reply_markup:
        payload['reply_markup'] = reply_markup
    try:
        r = requests.post(_url('editMessageText'), json=payload, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error('edit_message_text error chat_id=%s msg_id=%s: %s', chat_id, message_id, e)
        return None


def delete_message(chat_id: int, message_id: int) -> dict | None:
    payload = {'chat_id': chat_id, 'message_id': message_id}
    try:
        r = requests.post(_url('deleteMessage'), json=payload, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error('delete_message error chat_id=%s msg_id=%s: %s', chat_id, message_id, e)
        return None


def send_document(chat_id: int, file_path: str, caption: str = '') -> dict | None:
    """
    Отправить файл (документ) пользователю через sendDocument.

    :param chat_id:   Telegram chat_id получателя
    :param file_path: абсолютный путь к файлу на диске
    :param caption:   подпись к файлу (опционально, до 1024 символов)
    """
    try:
        with open(file_path, 'rb') as f:
            files = {'document': f}
            data = {'chat_id': chat_id}
            if caption:
                data['caption'] = caption[:1024]
            resp = requests.post(_url('sendDocument'), data=data, files=files, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except FileNotFoundError:
        logger.error('send_document: файл не найден: %s', file_path)
        return None
    except Exception as e:
        logger.error('send_document error chat_id=%s file=%s: %s', chat_id, file_path, e)
        return None

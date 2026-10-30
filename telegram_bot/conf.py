"""Настройки бота и отправка сообщений без задержки HTTP-запросов сайта."""
import logging
import threading

from django.conf import settings

from .api import TelegramAPI, TelegramError

logger = logging.getLogger('telegram_bot')


def enabled():
    return bool(getattr(settings, 'TELEGRAM_BOT_TOKEN', ''))


def get_api():
    return TelegramAPI(settings.TELEGRAM_BOT_TOKEN)


def staff_chat_id():
    raw = str(getattr(settings, 'TELEGRAM_STAFF_CHAT_ID', '') or '').strip()
    try:
        return int(raw) if raw else None
    except ValueError:
        logger.error("TELEGRAM_STAFF_CHAT_ID должен быть числом, сейчас: %r", raw)
        return None


def bot_username():
    return getattr(settings, 'TELEGRAM_BOT_USERNAME', '')


def site_url(path=''):
    return getattr(settings, 'SITE_URL', '').rstrip('/') + path


def send_later(chat_id, text, keyboard=None):
    """Отправляет сообщение в фоне: сайт не ждёт ответа Telegram и не падает от его ошибок.

    В тестах (TELEGRAM_SEND_SYNC = True) отправка синхронная, чтобы её можно было проверить.
    """
    if not enabled() or chat_id is None:
        return

    def run():
        try:
            get_api().send_message(chat_id, text, keyboard)
        except TelegramError as error:
            logger.warning("Сообщение в Telegram не отправлено: %s", error)

    if getattr(settings, 'TELEGRAM_SEND_SYNC', False):
        run()
    else:
        threading.Thread(target=run, daemon=True).start()

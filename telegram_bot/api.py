"""Минимальный клиент Telegram Bot API на стандартной библиотеке.

Нужны всего несколько методов, поэтому отдельная зависимость не подключается.
Токен никогда не попадает в текст исключений и логи.
"""
import json
import urllib.error
import urllib.request


class TelegramError(Exception):
    pass


class TelegramAPI:
    BASE = 'https://api.telegram.org'

    def __init__(self, token, timeout=10):
        self._token = token
        self.timeout = timeout

    def call(self, method, params=None, timeout=None):
        url = f"{self.BASE}/bot{self._token}/{method}"
        body = json.dumps({k: v for k, v in (params or {}).items() if v is not None}).encode('utf-8')
        request = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=timeout or self.timeout) as response:
                payload = json.loads(response.read())
        except urllib.error.HTTPError as error:
            try:
                payload = json.loads(error.read())
            except ValueError:
                raise TelegramError(f"{method}: HTTP {error.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            reason = getattr(error, 'reason', error)
            raise TelegramError(f"{method}: нет связи с Telegram ({reason})") from None

        if not payload.get('ok'):
            raise TelegramError(f"{method}: {payload.get('description', 'неизвестная ошибка')}")
        return payload.get('result')

    # ------------------------------------------------------------------ обёртки
    def get_me(self):
        return self.call('getMe')

    def delete_webhook(self):
        return self.call('deleteWebhook')

    def get_updates(self, offset=None, timeout=25):
        return self.call(
            'getUpdates',
            {'offset': offset, 'timeout': timeout, 'allowed_updates': ['message', 'callback_query']},
            timeout=timeout + 10,
        )

    def send_message(self, chat_id, text, keyboard=None):
        return self.call('sendMessage', {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True,
            'reply_markup': {'inline_keyboard': keyboard} if keyboard else None,
        })

    def edit_message(self, chat_id, message_id, text, keyboard=None):
        return self.call('editMessageText', {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True,
            'reply_markup': {'inline_keyboard': keyboard or []},
        })

    def answer_callback(self, callback_id, text=''):
        return self.call('answerCallbackQuery', {'callback_query_id': callback_id, 'text': text})

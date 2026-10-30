"""Разбор входящих обновлений Telegram: кнопки персонала, команды ресепшн, команды гостей."""
import logging

from django.utils import timezone

from . import conf, daily, guest, staff

logger = logging.getLogger('telegram_bot')


def handle_update(api, update):
    if 'callback_query' in update:
        callback = update['callback_query']
        if callback.get('data', '').startswith(staff.CALLBACK_PREFIX + ':'):
            staff.handle_callback(api, callback)
        else:
            api.answer_callback(callback['id'])
        return

    message = update.get('message')
    if not message or 'text' not in message:
        return
    chat_id = message['chat']['id']
    command = message['text'].strip().split()[0].split('@')[0].lower() if message['text'].strip() else ''

    if command == '/chatid':
        api.send_message(chat_id, f"ID этого чата: <code>{chat_id}</code>\nУкажите его в TELEGRAM_STAFF_CHAT_ID, чтобы сюда приходили брони.")
        return

    if chat_id == conf.staff_chat_id():
        if command == '/today':
            api.send_message(chat_id, daily.build_digest(timezone.localdate()))
        elif command in ('/start', '/help'):
            api.send_message(chat_id, (
                "Это чат ресепшн. Сюда приходят новые брони с кнопками подтверждения "
                "и каждое утро сводка по отелю.\n\n/today · сводка прямо сейчас"
            ))
        return   # обычная переписка персонала боту не адресована

    if message['chat'].get('type') == 'private':
        guest.handle_message(api, message)

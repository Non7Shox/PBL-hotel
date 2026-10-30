"""Чат персонала: новые брони с кнопками, смена статусов, команды ресепшн."""
from html import escape

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from bookings.models import Booking

from . import conf

# Подписи кнопок для переходов статуса (как в панели персонала)
ACTION_LABELS = {
    Booking.STATUS_CONFIRMED: "Подтвердить",
    Booking.STATUS_CHECKED_IN: "Заселить",
    Booking.STATUS_CHECKED_OUT: "Выселить",
    Booking.STATUS_CANCELLED: "Отменить",
    Booking.STATUS_NO_SHOW: "Не приехал",
}
# Что показывать кнопками: «не приехал» оставляем для панели, чтобы не нажать случайно
BUTTON_STATUSES = (
    Booking.STATUS_CONFIRMED,
    Booking.STATUS_CHECKED_IN,
    Booking.STATUS_CHECKED_OUT,
    Booking.STATUS_CANCELLED,
)
CALLBACK_PREFIX = 'st'


def booking_card(booking, title):
    """Карточка брони для чата персонала (HTML Telegram, данные гостя экранированы)."""
    source = 'стойка' if booking.source == 'desk' else 'сайт'
    lines = [
        f"<b>{escape(title)}</b>",
        "",
        f"<b>{escape(booking.code)}</b> · {escape(booking.room.title)}, номер {escape(booking.room.display_number)}",
        f"{booking.check_in:%d.%m} → {booking.check_out:%d.%m.%Y} · ночей: {booking.nights} · гостей: {booking.guests}",
        f"Итого: <b>${booking.total_price}</b>",
        "",
        f"Гость: {escape(booking.guest_name)}",
        f"Телефон: {escape(booking.guest_phone or 'не указан')}",
        f"Почта: {escape(booking.guest_email)}",
    ]
    if booking.special_requests:
        lines.append(f"Пожелания: {escape(booking.special_requests)}")
    lines += ["", f"Статус: <b>{escape(booking.get_status_display())}</b> · источник: {source}"]
    return "\n".join(lines)


def keyboard(booking):
    buttons = [
        {'text': ACTION_LABELS[status], 'callback_data': f"{CALLBACK_PREFIX}:{booking.pk}:{status}"}
        for status in booking.available_statuses
        if status in BUTTON_STATUSES
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    # Telegram не принимает в кнопках ссылки на localhost, поэтому ссылка — только для публичного адреса
    if conf.site_url().startswith('https://'):
        rows.append([{'text': "Открыть в панели", 'url': conf.site_url('/staff/')}])
    return rows or None


def notify_new_booking(booking):
    conf.send_later(conf.staff_chat_id(), booking_card(booking, "Новая заявка на бронь"), keyboard(booking))


def notify_status(booking, actor=''):
    who = f" ({escape(actor)})" if actor else ""
    text = (
        f"<b>{escape(booking.code)}</b> · {escape(booking.room.title)}: "
        f"{escape(booking.get_status_display().lower())}{who}"
    )
    conf.send_later(conf.staff_chat_id(), text, keyboard(booking) if booking.available_statuses else None)


def handle_callback(api, callback):
    """Нажатие кнопки под карточкой брони. Принимается только из чата персонала."""
    message = callback.get('message') or {}
    chat_id = (message.get('chat') or {}).get('id')
    if chat_id is None or chat_id != conf.staff_chat_id():
        api.answer_callback(callback['id'], "Эти кнопки работают только в чате ресепшн.")
        return

    try:
        _prefix, pk, new_status = callback.get('data', '').split(':')
        pk = int(pk)
    except ValueError:
        api.answer_callback(callback['id'], "Не удалось разобрать команду.")
        return

    user = callback.get('from') or {}
    actor = user.get('username') and f"@{user['username']}" or user.get('first_name') or "сотрудник"

    with transaction.atomic():
        booking = Booking.objects.select_for_update().select_related('room').filter(pk=pk).first()
        if booking is None:
            api.answer_callback(callback['id'], "Бронь не найдена.")
            return
        try:
            booking.set_status(new_status)
        except ValidationError as error:
            api.answer_callback(callback['id'], error.messages[0])
            api.edit_message(chat_id, message['message_id'], booking_card(booking, "Бронь"), keyboard(booking))
            return

    from bookings import notify
    notify.status_changed(booking, actor=actor, source='telegram')

    stamp = timezone.localtime().strftime('%H:%M')
    text = booking_card(booking, "Бронь обновлена") + f"\n{escape(actor)}, {stamp}"
    api.edit_message(chat_id, message['message_id'], text, keyboard(booking))
    api.answer_callback(callback['id'], f"{booking.code}: {booking.get_status_display()}")

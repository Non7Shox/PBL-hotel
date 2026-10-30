"""Единая точка уведомлений по броням: письма + Telegram.

Вьюхи вызывают только эти функции, а куда именно уходит сообщение
(почта гостю, чат ресепшн, Telegram гостя) решается здесь.
"""
from .emails import notify_booking_created, notify_booking_status


def booking_created(booking):
    """Новая бронь: письмо гостю и копия на стойку, сообщение в чат персонала."""
    notify_booking_created(booking)
    from telegram_bot import staff
    staff.notify_new_booking(booking)


def status_changed(booking, actor='', source='site'):
    """Статус брони изменился.

    source='telegram' — изменение сделано кнопкой в чате персонала; там сообщение
    обновляется на месте, поэтому отдельное уведомление в чат не нужно.
    """
    notify_booking_status(booking)
    from telegram_bot import guest, staff
    guest.notify_status(booking)
    if source != 'telegram':
        staff.notify_status(booking, actor)

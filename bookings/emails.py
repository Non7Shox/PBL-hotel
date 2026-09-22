"""E-mail-уведомления по бронированию.

При MAILERS.default = console.EmailBackend письма печатаются прямо в консоль,
что удобно для демонстрации проекта: заявка гостя, копия на стойку регистрации
и сообщение о смене статуса видны в терминале запуска сервера.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _hotel_email():
    return getattr(settings, 'HOTEL_NOTIFY_EMAIL', '')


def _from_email():
    return getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@aureliohotel.uz')


def _send(subject, body, recipients):
    recipients = [email for email in recipients if email]
    if not recipients:
        return 0
    try:
        return send_mail(subject, body, _from_email(), recipients)
    except Exception:  # pragma: no cover - почта не должна ломать бронирование
        logger.exception("Не удалось отправить письмо: %s", subject)
        return 0


def booking_summary(booking):
    """Текстовая сводка брони, общая для всех писем."""
    return '\n'.join([
        f"Код брони: {booking.code}",
        f"Номер: {booking.room.title}",
        f"Заезд: {booking.check_in:%d.%m.%Y} (с 14:00)",
        f"Выезд: {booking.check_out:%d.%m.%Y} (до 12:00)",
        f"Ночей: {booking.nights}",
        f"Гостей: {booking.guests}",
        f"Итого: {booking.total_price} $",
        f"Гость: {booking.guest_name}",
        f"Телефон: {booking.guest_phone or '—'}",
        f"E-mail: {booking.guest_email}",
        f"Статус: {booking.get_status_display()}",
    ])


def notify_booking_created(booking):
    """Письмо гостю с подтверждением получения заявки + копия на стойку."""
    guest_body = '\n'.join([
        f"Здравствуйте, {booking.guest_name}!",
        '',
        'Мы получили вашу заявку на бронирование в отеле Aurelio.',
        'Администратор подтвердит её в течение 15 минут.',
        '',
        booking_summary(booking),
        '',
        'Проверить бронь можно по коду на сайте: /bookings/lookup/',
        'Отмена без штрафа — не позднее чем за 24 часа до заезда.',
        '',
        'Aurelio Hotel · Ташкент · +998 (90) 000-00-00',
    ])
    _send(f"Заявка на бронь {booking.code} принята", guest_body, [booking.guest_email])

    staff_body = '\n'.join([
        'НОВАЯ ЗАЯВКА НА БРОНИРОВАНИЕ',
        '',
        booking_summary(booking),
        '',
        f"Пожелания гостя: {booking.special_requests or '—'}",
        'Открыть в панели персонала: /staff/',
    ])
    _send(f"[Новая бронь] {booking.code} · {booking.room.title}", staff_body, [_hotel_email()])


def notify_booking_status(booking):
    """Информирует гостя о смене статуса брони."""
    templates = {
        'confirmed': (
            f"Бронь {booking.code} подтверждена",
            "Ваша бронь подтверждена. Ждём вас! Заезд с 14:00, выезд до 12:00.",
        ),
        'checked_in': (
            f"Заселение по брони {booking.code}",
            "Приятного отдыха! Если что-то понадобится — звоните на ресепшн.",
        ),
        'checked_out': (
            f"Выезд по брони {booking.code}",
            "Спасибо, что были нашим гостем. Будем рады отзыву о номере на сайте.",
        ),
        'cancelled': (
            f"Бронь {booking.code} отменена",
            "Бронь отменена. Если это ошибка — свяжитесь с ресепшн по телефону +998 (90) 000-00-00.",
        ),
        'no_show': (
            f"Бронь {booking.code}: отметка «не приехал»",
            "Мы отметили бронь как неиспользованную. Позвоните нам, если хотите перенести даты.",
        ),
    }
    subject, intro = templates.get(
        booking.status, (f"Статус брони {booking.code} обновлён", "Статус вашей брони изменился.")
    )
    body = '\n'.join([f"Здравствуйте, {booking.guest_name}!", '', intro, '', booking_summary(booking), '', 'Aurelio Hotel'])
    return _send(subject, body, [booking.guest_email])

"""Бот для гостей: подписка на бронь, статус, свободные номера, напоминания."""
import hmac
import re
from datetime import date, timedelta
from html import escape

from django.utils import timezone
from django.utils.crypto import salted_hmac

from bookings.models import Booking
from rooms.models import Room

from . import conf

LINK_SALT = 'telegram_bot.booking-link'
CODE_RE = re.compile(r'^AUR-[A-Z0-9]{6}$')

HELP = (
    "Это бот отеля <b>Aurelio Hotel</b>.\n\n"
    "/booking <i>КОД почта</i> · подключить уведомления по брони\n"
    "/mybookings · ваши подключённые брони\n"
    "/rooms <i>12.11 15.11</i> · свободные номера на даты\n"
    "/stop · отключить уведомления\n\n"
    "Код брони вида AUR и шесть символов есть в письме и на странице брони."
)

STATUS_TEXT = {
    Booking.STATUS_PENDING: "Заявка получена. Администратор подтвердит её в течение 15 минут.",
    Booking.STATUS_CONFIRMED: "Бронь подтверждена. Ждём вас: заезд с 14:00, выезд до 12:00.",
    Booking.STATUS_CHECKED_IN: "Вы заселены. Ресепшн работает круглосуточно: +998 (90) 000 00 00.",
    Booking.STATUS_CHECKED_OUT: "Выезд оформлен. Спасибо, что выбрали Aurelio. Будем рады отзыву о номере на сайте.",
    Booking.STATUS_CANCELLED: "Бронь отменена. Если это ошибка, позвоните на ресепшн: +998 (90) 000 00 00.",
    Booking.STATUS_NO_SHOW: "Бронь отмечена как неиспользованная. Позвоните нам, если хотите перенести даты.",
}


# ------------------------------------------------------------------ ссылка для подписки
def _signature(code):
    return salted_hmac(LINK_SALT, code).hexdigest()[:16]


def link_payload(booking):
    """Параметр /start: код брони + подпись. Только символы, которые разрешает Telegram."""
    return f"{booking.code}_{_signature(booking.code)}"


def booking_from_payload(payload):
    code, _, signature = payload.partition('_')
    if not CODE_RE.match(code) or not hmac.compare_digest(signature, _signature(code)):
        return None
    return Booking.objects.select_related('room').filter(code=code).first()


def telegram_link(booking):
    """Ссылка «подключить уведомления» для страницы брони; None, если бот не настроен."""
    username = conf.bot_username()
    if not (conf.enabled() and username):
        return None
    return f"https://t.me/{username}?start={link_payload(booking)}"


# ------------------------------------------------------------------ тексты
def booking_text(booking, intro=''):
    lines = []
    if intro:
        lines += [intro, ""]
    lines += [
        f"<b>{escape(booking.code)}</b> · {escape(booking.room.title)}",
        f"{booking.check_in:%d.%m.%Y} → {booking.check_out:%d.%m.%Y}, ночей: {booking.nights}",
        f"Итого: ${booking.total_price}, оплата при заселении",
        f"Статус: <b>{escape(booking.get_status_display())}</b>",
    ]
    return "\n".join(lines)


def notify_status(booking):
    if booking.telegram_chat_id:
        conf.send_later(booking.telegram_chat_id, booking_text(booking, STATUS_TEXT.get(booking.status, '')))


def reminder_text(booking):
    return booking_text(
        booking,
        f"Напоминаем: завтра, {booking.check_in:%d.%m}, ваш заезд в Aurelio Hotel. "
        "Номер будет готов с 14:00. Адрес: Ташкент, ул. Примерная, 1.",
    )


# ------------------------------------------------------------------ команды
def _link(api, chat_id, booking):
    Booking.objects.filter(pk=booking.pk).update(telegram_chat_id=chat_id)
    booking.telegram_chat_id = chat_id
    api.send_message(chat_id, booking_text(
        booking, "Уведомления подключены. Сюда придёт подтверждение брони и напоминание за день до заезда.",
    ))


def cmd_start(api, chat_id, args):
    if args:
        booking = booking_from_payload(args[0])
        if booking is None:
            api.send_message(chat_id, "Ссылка устарела или повреждена. Подключите бронь командой /booking КОД почта.")
            return
        _link(api, chat_id, booking)
        return
    api.send_message(chat_id, HELP)


def cmd_booking(api, chat_id, args):
    if len(args) != 2:
        api.send_message(chat_id, "Напишите код брони и почту через пробел, например:\n/booking AUR-7K4P2C name@mail.uz")
        return
    code, email = args[0].upper(), args[1]
    booking = Booking.objects.select_related('room').filter(code=code, guest_email__iexact=email).first()
    if booking is None:
        api.send_message(chat_id, "Бронь с таким кодом и почтой не найдена. Проверьте код в письме о бронировании.")
        return
    _link(api, chat_id, booking)


def cmd_mybookings(api, chat_id, args):
    bookings = Booking.objects.select_related('room').filter(telegram_chat_id=chat_id).order_by('check_in')
    if not bookings:
        api.send_message(chat_id, "Подключённых броней нет. Подключите бронь командой /booking КОД почта.")
        return
    api.send_message(chat_id, "\n\n".join(booking_text(b) for b in bookings))


def cmd_stop(api, chat_id, args):
    count = Booking.objects.filter(telegram_chat_id=chat_id).update(telegram_chat_id=None)
    api.send_message(chat_id, f"Уведомления отключены, броней: {count}." if count else "Подключённых броней не было.")


def _parse_day(text, today):
    match = re.fullmatch(r'(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?', text)
    if not match:
        return None
    day, month, year = match.groups()
    year = int(year) + (2000 if year and len(year) == 2 else 0) if year else today.year
    try:
        value = date(year, int(month), int(day))
    except ValueError:
        return None
    if not match.group(3) and value < today:
        value = date(year + 1, int(month), int(day))
    return value


def free_rooms(check_in, check_out, guests=1):
    busy = Booking.objects.filter(
        status__in=Booking.ACTIVE_STATUSES, check_in__lt=check_out, check_out__gt=check_in,
    ).values('room_id')
    rooms = (
        Room.objects.filter(is_active=True, capacity__gte=guests)
        .exclude(housekeeping='out_of_service')
        .exclude(pk__in=busy)
        .order_by('price_per_night')
    )
    return [(room, room.get_price_for_dates(check_in, check_out)) for room in rooms]


def cmd_rooms(api, chat_id, args):
    today = timezone.localdate()
    if not args:
        check_in, check_out, guests = today, today + timedelta(days=1), 1
    else:
        check_in = _parse_day(args[0], today)
        check_out = _parse_day(args[1], today) if len(args) > 1 else (check_in and check_in + timedelta(days=1))
        guests = int(args[2]) if len(args) > 2 and args[2].isdigit() else 1
        if not check_in or not check_out:
            api.send_message(chat_id, "Укажите даты в формате ДД.ММ, например:\n/rooms 12.11 15.11 2")
            return
    if check_in < today or check_out <= check_in:
        api.send_message(chat_id, "Дата выезда должна быть позже даты заезда, а заезд не раньше сегодняшнего дня.")
        return

    nights = (check_out - check_in).days
    found = free_rooms(check_in, check_out, guests)
    header = f"Свободно {check_in:%d.%m} → {check_out:%d.%m}, ночей: {nights}, гостей: {guests}"
    if not found:
        api.send_message(chat_id, f"{header}\n\nНа эти даты свободных номеров нет. Попробуйте сдвинуть даты на день.")
        return
    lines = [f"<b>{header}</b>", ""]
    for room, total in found[:10]:
        lines.append(
            f"<b>{escape(room.title)}</b>, номер {escape(room.display_number)}, до {room.capacity} гостей\n"
            f"${total} за весь срок · {conf.site_url(f'/bookings/new/{room.pk}/')}"
        )
    api.send_message(chat_id, "\n\n".join(lines))


COMMANDS = {
    '/start': cmd_start,
    '/help': cmd_start,
    '/booking': cmd_booking,
    '/mybookings': cmd_mybookings,
    '/stop': cmd_stop,
    '/rooms': cmd_rooms,
}


def handle_message(api, message):
    chat_id = message['chat']['id']
    text = (message.get('text') or '').strip()
    if not text.startswith('/'):
        api.send_message(chat_id, HELP)
        return
    command, *args = text.split()
    command = command.split('@')[0].lower()   # /rooms@AurelioBot в группах
    handler = COMMANDS.get(command)
    if handler is None:
        api.send_message(chat_id, "Такой команды нет.\n\n" + HELP)
        return
    handler(api, chat_id, args)

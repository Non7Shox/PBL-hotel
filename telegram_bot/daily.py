"""Утренняя сводка для руководства и напоминания гостям о завтрашнем заезде."""
from datetime import timedelta
from html import escape

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from bookings.models import Booking
from rooms.models import Room

from . import conf, guest
from .models import DailyDigest


def build_digest(day):
    tomorrow = day + timedelta(days=1)
    bookings = Booking.objects.select_related('room')
    active_rooms = Room.objects.filter(is_active=True).count()

    arrivals = bookings.filter(check_in=day, status__in=(Booking.STATUS_PENDING, Booking.STATUS_CONFIRMED)).order_by('room__room_number')
    departures = bookings.filter(check_out=day, status=Booking.STATUS_CHECKED_IN).order_by('room__room_number')
    in_house = bookings.filter(status=Booking.STATUS_CHECKED_IN).count()
    pending = bookings.filter(status=Booking.STATUS_PENDING)
    busy_tonight = bookings.filter(
        status__in=Booking.ACTIVE_STATUSES, check_in__lt=tomorrow, check_out__gt=day,
    ).values('room_id').distinct().count()
    occupancy = round(busy_tonight * 100 / active_rooms) if active_rooms else 0
    revenue = bookings.filter(
        status=Booking.STATUS_CHECKED_OUT, check_out__year=day.year, check_out__month=day.month,
    ).aggregate(total=Sum('total_price'))['total'] or 0

    def listing(items, empty):
        if not items:
            return [f"  {empty}"]
        return [
            f"  {escape(b.code)} · {escape(b.room.title)} · {escape(b.guest_name)}"
            + (" · <i>не подтверждена</i>" if b.status == Booking.STATUS_PENDING else "")
            for b in items
        ]

    lines = [
        f"<b>Сводка на {day:%d.%m.%Y}</b>",
        "",
        f"Загрузка на ночь: <b>{occupancy}%</b> ({busy_tonight} из {active_rooms} номеров)",
        f"Гостей в отеле: {in_house}",
        f"Новых заявок ждут ответа: <b>{pending.count()}</b>",
        f"Выручка за месяц по выездам: ${revenue}",
        "",
        f"<b>Заезды сегодня: {len(arrivals)}</b>",
        *listing(list(arrivals), "заездов нет"),
        "",
        f"<b>Выезды сегодня: {len(departures)}</b>",
        *listing(list(departures), "выездов нет"),
    ]
    return "\n".join(lines)


def send_reminders(api, day):
    """Напоминание гостям, у которых заезд завтра и подключён Telegram. Каждому один раз."""
    due = Booking.objects.select_related('room').filter(
        check_in=day + timedelta(days=1),
        status__in=(Booking.STATUS_PENDING, Booking.STATUS_CONFIRMED),
        telegram_chat_id__isnull=False,
        reminder_sent_at__isnull=True,
    )
    sent = 0
    for booking in due:
        api.send_message(booking.telegram_chat_id, guest.reminder_text(booking))
        Booking.objects.filter(pk=booking.pk).update(reminder_sent_at=timezone.now())
        sent += 1
    return sent


def run_daily(api, day=None, force=False):
    """Напоминания гостям и сводка в чат персонала.

    Напоминания уходят всегда: каждая бронь помечается reminder_sent_at, поэтому дублей нет.
    Сводка отмечается отправленной только если чат персонала настроен — иначе, добавив чат
    позже в тот же день, ресепшн её уже не получил бы. Возвращает запись о сводке или None.
    """
    day = day or timezone.localdate()
    reminders = send_reminders(api, day)

    chat_id = conf.staff_chat_id()
    if chat_id is None:
        return None
    if not force:
        try:
            # Отдельная точка сохранения: уникальная дата защищает от двойной отправки,
            # даже если бот и планировщик запустят рассылку одновременно.
            with transaction.atomic():
                record = DailyDigest.objects.create(date=day)
        except IntegrityError:
            return None
    else:
        record, _ = DailyDigest.objects.get_or_create(date=day)

    api.send_message(chat_id, build_digest(day))
    record.reminders = reminders
    record.save(update_fields=['reminders'])
    return record


def due_now():
    """Пора ли слать сводку: наступил настроенный час, а за сегодня ещё не отправляли."""
    now = timezone.localtime()
    from django.conf import settings
    return now.hour >= settings.TELEGRAM_DIGEST_HOUR and not DailyDigest.objects.filter(date=now.date()).exists()

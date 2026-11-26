"""Расчёты для шахматки и аналитики."""

from datetime import timedelta
from decimal import Decimal

from bookings.models import Booking
from rooms.models import Room

# брони, которые занимают номер и приносят выручку
COUNTED_STATUSES = Booking.ACTIVE_STATUSES + (Booking.STATUS_CHECKED_OUT,)


def _bookings_between(start, end):
    return (
        Booking.objects.select_related('room')
        .filter(status__in=COUNTED_STATUSES, check_in__lt=end, check_out__gt=start)
        .order_by('check_in', 'pk')
    )


def occupancy_grid(start, days):
    """Строки шахматки: у каждого номера список ячеек; бронь растянута на span дней."""
    end = start + timedelta(days=days)
    by_room = {}
    for booking in _bookings_between(start, end):
        by_room.setdefault(booking.room_id, []).append(booking)

    rows = []
    for room in Room.objects.filter(is_active=True).order_by('room_number', 'pk'):
        cells, day = [], start
        for booking in by_room.get(room.pk, []):
            first = max(booking.check_in, day)  # пересечения не должны ломать сетку
            last = min(booking.check_out, end)
            if last <= first:
                continue
            while day < first:
                cells.append({'date': day, 'booking': None, 'span': 1})
                day += timedelta(days=1)
            cells.append({'date': day, 'booking': booking, 'span': (last - first).days})
            day = last
        while day < end:
            cells.append({'date': day, 'booking': None, 'span': 1})
            day += timedelta(days=1)
        rows.append({'room': room, 'cells': cells})
    return rows


def analytics(start, days):
    """Загрузка и выручка по ночам, а также рейтинг номеров за период."""
    end = start + timedelta(days=days)
    room_ids = set(Room.objects.filter(is_active=True).values_list('pk', flat=True))
    daily = [{'date': start + timedelta(days=i), 'rooms': set(), 'revenue': Decimal(0)} for i in range(days)]
    top = {}

    for booking in _bookings_between(start, end):
        if booking.room_id not in room_ids or not booking.nights:
            continue
        per_night = (booking.total_price or Decimal(0)) / booking.nights
        night = max(booking.check_in, start)
        while night < min(booking.check_out, end):
            slot = daily[(night - start).days]
            slot['rooms'].add(booking.room_id)
            slot['revenue'] += per_night
            entry = top.setdefault(booking.room_id, {'room': booking.room, 'nights': 0, 'revenue': Decimal(0)})
            entry['nights'] += 1
            entry['revenue'] += per_night
            night += timedelta(days=1)

    peak = max((slot['revenue'] for slot in daily), default=0)
    for slot in daily:
        slot['occupancy'] = round(len(slot['rooms']) * 100 / len(room_ids)) if room_ids else 0
        slot['revenue_height'] = round(slot['revenue'] * 100 / peak) if peak else 0

    sold = sum(len(slot['rooms']) for slot in daily)
    revenue = sum((slot['revenue'] for slot in daily), Decimal(0))
    available = len(room_ids) * days
    ranking = sorted(top.values(), key=lambda e: -e['revenue'])[:5]
    for entry in ranking:
        entry['share'] = round(entry['revenue'] * 100 / ranking[0]['revenue']) if ranking[0]['revenue'] else 0

    return {
        'daily': daily,
        'ranking': ranking,
        'revenue': revenue,
        'nights_sold': sold,
        'occupancy': round(sold * 100 / available) if available else 0,
        # ADR — средний тариф проданной ночи; RevPAR — выручка на доступную ночь
        'adr': revenue / sold if sold else 0,
        'revpar': revenue / available if available else 0,
    }

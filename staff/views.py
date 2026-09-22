from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from bookings.emails import notify_booking_created, notify_booking_status
from bookings.models import Booking
from rooms.models import Floor, Room

from .decorators import staff_required
from .forms import DeskBookingForm

STATUS_COLUMNS = [
    (Booking.STATUS_PENDING, "Новые заявки"),
    (Booking.STATUS_CONFIRMED, "Подтверждённые"),
    (Booking.STATUS_CHECKED_IN, "В отеле"),
]

ACTION_LABELS = {
    Booking.STATUS_CONFIRMED: "Подтвердить",
    Booking.STATUS_CHECKED_IN: "Заселить",
    Booking.STATUS_CHECKED_OUT: "Выселить",
    Booking.STATUS_CANCELLED: "Отменить",
    Booking.STATUS_NO_SHOW: "Не приехал",
}

STATUS_CSS = {
    Booking.STATUS_PENDING: 'status-pending',
    Booking.STATUS_CONFIRMED: 'status-confirmed',
    Booking.STATUS_CHECKED_IN: 'status-in',
    Booking.STATUS_CHECKED_OUT: 'status-out',
    Booking.STATUS_CANCELLED: 'status-cancelled',
    Booking.STATUS_NO_SHOW: 'status-noshow',
}


@staff_required
def dashboard(request):
    """Пульт ресепшена: загрузка, заезды, выезды, требующие внимания заявки."""
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    bookings = Booking.objects.select_related('room', 'room__floor')

    arrivals = bookings.filter(check_in=today, status__in=(Booking.STATUS_PENDING, Booking.STATUS_CONFIRMED))
    departures = bookings.filter(check_out=today, status=Booking.STATUS_CHECKED_IN)
    in_house = bookings.filter(status=Booking.STATUS_CHECKED_IN)

    context = {
        'today': today,
        'arrivals': arrivals,
        'departures': departures,
        'in_house': in_house,
        'pending': bookings.filter(status=Booking.STATUS_PENDING).order_by('check_in')[:10],
        'upcoming': bookings.filter(
            check_in__gt=today, status__in=(Booking.STATUS_PENDING, Booking.STATUS_CONFIRMED)
        ).order_by('check_in')[:10],
        'columns': [
            (label, bookings.filter(status=status).order_by('check_in')[:12])
            for status, label in STATUS_COLUMNS
        ],
        'kpi': {
            'arrivals': arrivals.count(),
            'departures': departures.count(),
            'in_house': in_house.count(),
            'pending': bookings.filter(status=Booking.STATUS_PENDING).count(),
            'free_tonight': Room.objects.filter(is_active=True)
            .exclude(bookings__status__in=Booking.ACTIVE_STATUSES)
            .distinct()
            .count(),
        },
        'occupancy': _occupancy(bookings, today, tomorrow),
        'revenue_month': bookings.filter(
            status=Booking.STATUS_CHECKED_OUT, check_out__year=today.year, check_out__month=today.month
        ).aggregate(total=Sum('total_price'))['total'] or 0,
        'action_labels': ACTION_LABELS,
        'status_css': STATUS_CSS,
    }
    return render(request, 'staff/dashboard.html', context)


def _occupancy(bookings, day, next_day):
    total = Room.objects.filter(is_active=True).count()
    if not total:
        return 0
    busy = bookings.filter(
        status__in=Booking.ACTIVE_STATUSES, check_in__lt=next_day, check_out__gt=day
    ).values('room_id').distinct().count()
    return round(busy * 100 / total)


@staff_required
def rooms_board(request):
    """Список номеров: статус уборки, кто живёт сейчас, ближайший заезд."""
    today = timezone.localdate()
    rooms = (
        Room.objects.select_related('floor')
        .annotate(
            active_bookings=Count('bookings', filter=Q(bookings__status__in=Booking.ACTIVE_STATUSES)),
        )
        .order_by('floor__number', 'room_number')
    )
    context = {
        'floors': Floor.objects.all().order_by('number'),
        'rooms': rooms,
        'occupied_ids': set(
            Booking.objects.filter(
                status=Booking.STATUS_CHECKED_IN, check_in__lte=today, check_out__gt=today
            ).values_list('room_id', flat=True)
        ),
        'today': today,
    }
    return render(request, 'staff/rooms_board.html', context)


@staff_required
def desk_booking(request):
    """Ручное бронирование на стойке — для звонков и гостей без интернета."""
    form = DeskBookingForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        booking = form.save()
        notify_booking_created(booking)
        messages.success(request, f"Бронь {booking.code} создана на стойке.")
        return redirect('bookings:booking_detail', code=booking.code)

    context = {
        'form': form,
        'recent': Booking.objects.select_related('room').order_by('-created_at')[:8],
    }
    return render(request, 'staff/desk_booking.html', context)


@staff_required
@require_POST
def booking_action(request, pk, action):
    """Смена статуса брони сотрудником: подтвердить, заселить, выселить, отменить."""
    booking = get_object_or_404(Booking.objects.select_related('room'), pk=pk)
    try:
        booking.set_status(action)
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        notify_booking_status(booking)
        messages.success(request, f"{booking.code}: {booking.get_status_display()}")

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    return redirect(next_url or 'staff:dashboard')


@staff_required
@require_POST
def housekeeping_action(request, pk):
    """Служба уборки / менеджер меняет статус готовности номера."""
    room = get_object_or_404(Room, pk=pk)
    new_status = request.POST.get('housekeeping')
    valid = {value for value, _label in Room.HOUSEKEEPING_CHOICES}
    if new_status not in valid:
        messages.error(request, "Неизвестный статус уборки.")
    else:
        room.housekeeping = new_status
        room.save(update_fields=['housekeeping'])
        messages.success(request, f"Номер {room.display_number}: {room.get_housekeeping_display()}")
    return redirect('staff:rooms_board')


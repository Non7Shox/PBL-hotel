from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from rooms.models import Room
from staff.decorators import is_staff_member

from .emails import notify_booking_created, notify_booking_status
from .forms import BookingForm, BookingLookupForm
from .models import Booking

CURRENCY = getattr(settings, 'HOTEL_CURRENCY', '$')


def _remember_booking(request, booking):
    """Запоминаем код брони в сессии: так гость без аккаунта видит свою бронь."""
    codes = [code for code in request.session.get('booking_codes', []) if code != booking.code]
    codes.append(booking.code)
    request.session['booking_codes'] = codes[-10:]


def _can_view(request, booking):
    if is_staff_member(request.user):
        return True
    if booking.user_id and request.user.is_authenticated and booking.user_id == request.user.id:
        return True
    return booking.code in request.session.get('booking_codes', [])


def _get_booking_or_none(request, code):
    booking = (
        Booking.objects.select_related('room', 'room__floor', 'user')
        .filter(code=(code or '').strip().upper())
        .first()
    )
    if booking and _can_view(request, booking):
        return booking
    return None


def _upcoming_bookings(room):
    return Booking.objects.filter(
        room=room,
        status__in=Booking.ACTIVE_STATUSES,
        check_out__gte=timezone.localdate(),
    ).order_by('check_in')


def booking_create(request, pk):
    """Онлайн-бронирование выбранного номера."""
    room = get_object_or_404(Room.objects.select_related('floor'), pk=pk)

    if not room.is_active:
        messages.error(request, "Этот номер временно снят с продажи.")
        return redirect('rooms:room_detail', pk=room.pk)

    initial = {'guests': 2 if room.capacity >= 2 else 1}
    form = BookingForm(request.POST or None, room=room, user=request.user, initial=initial)

    if request.method == 'POST' and form.is_valid():
        booking = form.save()
        _remember_booking(request, booking)
        notify_booking_created(booking)
        messages.success(request, f"Заявка принята! Код вашей брони — {booking.code}.")
        return redirect('bookings:booking_success', code=booking.code)

    context = {
        'room': room,
        'form': form,
        'upcoming': _upcoming_bookings(room),
        'currency': CURRENCY,
    }
    return render(request, 'bookings/booking_form.html', context)


def booking_success(request, code):
    """Страница подтверждения: код брони, детали, следующие шаги."""
    booking = _get_booking_or_none(request, code) or get_object_or_404(Booking, code=code.upper())
    return render(request, 'bookings/booking_success.html', {'booking': booking, 'currency': CURRENCY})


def booking_detail(request, code):
    """Детали брони с историей статусов и кнопкой отмены."""
    booking = _get_booking_or_none(request, code)
    if booking is None:
        messages.warning(request, "Бронь не найдена. Проверьте код брони и e-mail.")
        return redirect('bookings:booking_lookup')

    history = [(booking.created_at, "Заявка создана")]
    if booking.status != Booking.STATUS_PENDING and booking.status_changed_at:
        history.append((booking.status_changed_at, booking.get_status_display()))

    context = {
        'booking': booking,
        'history': history,
        'can_cancel': booking.is_cancellable,
        'currency': CURRENCY,
    }
    return render(request, 'bookings/booking_detail.html', context)


@require_POST
def booking_cancel(request, code):
    """Отмена брони гостем — не позднее 24 часов до заезда."""
    booking = _get_booking_or_none(request, code)
    if booking is None:
        messages.warning(request, "Бронь не найдена.")
        return redirect('bookings:booking_lookup')

    if not booking.is_cancellable:
        messages.error(request, "Эту бронь нельзя отменить онлайн — позвоните на ресепшн.")
        return redirect('bookings:booking_detail', code=booking.code)

    booking.cancel()
    notify_booking_status(booking)
    messages.info(request, f"Бронь {booking.code} отменена.")
    return redirect('bookings:booking_detail', code=booking.code)


@login_required
def my_bookings(request):
    """Все брони авторизованного гостя: активные и архив."""
    bookings = list(
        Booking.objects.filter(user=request.user)
        .select_related('room', 'room__floor')
        .order_by('-created_at')
    )
    context = {
        'active_bookings': [b for b in bookings if b.is_active],
        'history_bookings': [b for b in bookings if not b.is_active],
        'total_spent': sum(
            (b.total_price or 0) for b in bookings if b.status == Booking.STATUS_CHECKED_OUT
        ),
        'currency': CURRENCY,
    }
    return render(request, 'bookings/my_bookings.html', context)


def booking_lookup(request):
    """Поиск брони по коду и e-mail — для гостей без аккаунта."""
    form = BookingLookupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        booking = Booking.objects.filter(
            code=form.cleaned_data['code'],
            guest_email__iexact=form.cleaned_data['email'],
        ).first()
        if booking:
            _remember_booking(request, booking)
            return redirect('bookings:booking_detail', code=booking.code)
        form.add_error(None, "Бронь с таким кодом и e-mail не найдена. Проверьте данные из письма.")

    return render(request, 'bookings/booking_lookup.html', {'form': form})


def availability_api(request):
    """JSON-расчёт стоимости и доступности — используется в JS формы брони."""
    room_id = request.GET.get('room')
    raw_in = request.GET.get('check_in')
    raw_out = request.GET.get('check_out')

    if not (room_id and raw_in and raw_out):
        return JsonResponse({'ok': False, 'error': 'missing_params'}, status=400)

    room = get_object_or_404(Room, pk=room_id)
    try:
        check_in = datetime.strptime(raw_in, '%Y-%m-%d').date()
        check_out = datetime.strptime(raw_out, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'bad_date'}, status=400)

    payload = {
        'ok': True,
        'currency': CURRENCY,
        'price_per_night': float(room.price_per_night),
        'nights': 0,
        'total': 0.0,
        'available': False,
        'message': '',
    }

    if check_out <= check_in:
        payload['message'] = "Дата выезда должна быть позже даты заезда."
        return JsonResponse(payload)

    nights = (check_out - check_in).days
    payload['nights'] = nights
    payload['total'] = round(float(room.price_per_night) * nights, 2)
    payload['available'] = Booking.is_room_free(room, check_in, check_out)
    payload['message'] = (
        "Номер свободен на выбранные даты."
        if payload['available']
        else "На эти даты номер уже забронирован — выберите другой период."
    )
    return JsonResponse(payload)



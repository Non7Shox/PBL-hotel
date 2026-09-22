from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Min, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from bookings.forms import BookingForm
from bookings.models import Booking

from .forms import ReviewForm, RoomSearchForm
from .models import Floor, Review, Room


def _busy_room_ids(check_in, check_out):
    """ID номеров, занятых в указанном интервале."""
    return set(
        Booking.objects.filter(
            status__in=Booking.ACTIVE_STATUSES,
            check_in__lt=check_out,
            check_out__gt=check_in,
        ).values_list('room_id', flat=True)
    )


# 1. Главная страница отеля: статистика, доступные номера, отзывы
def room_list(request):
    today = timezone.localdate()
    rooms = (
        Room.objects.filter(is_active=True)
        .select_related('floor')
        .annotate(
            avg_rating=Avg('reviews__rating', filter=Q(reviews__is_published=True)),
        )
    )
    busy_today = _busy_room_ids(today, today + timedelta(days=1))
    featured = list(rooms)[:3]

    context = {
        'total_rooms': Room.objects.count(),
        'total_floors': Floor.objects.count(),
        'min_price': Room.objects.aggregate(Min('price_per_night'))['price_per_night__min'] or 0,
        'featured_rooms': featured,
        'free_today_count': max(Room.objects.filter(is_active=True).count() - len(busy_today), 0),
        'avg_rating': Review.objects.filter(is_published=True).aggregate(value=Avg('rating'))['value'],
        'reviews_count': Review.objects.filter(is_published=True).count(),
        'latest_reviews': Review.objects.filter(is_published=True).select_related('user', 'room')[:3],
        'search_form': RoomSearchForm(),
        'today': today,
    }
    return render(request, 'rooms/room_list.html', context)


# 2. Подбор свободных номеров на выбранные даты
def room_search(request):
    """Результаты поиска: какие номера свободны, сколько стоят за весь срок."""
    form = RoomSearchForm(request.GET or None)
    results = []
    nights = 0
    searched = bool(request.GET)

    if searched and form.is_valid():
        check_in = form.cleaned_data['check_in']
        check_out = form.cleaned_data['check_out']
        guests = form.cleaned_data['guests']
        floor = form.cleaned_data.get('floor')
        max_price = form.cleaned_data.get('max_price')
        nights = (check_out - check_in).days
        busy_ids = _busy_room_ids(check_in, check_out)

        rooms = (
            Room.objects.filter(is_active=True, capacity__gte=guests)
            .select_related('floor')
            .annotate(
                avg_rating=Avg('reviews__rating', filter=Q(reviews__is_published=True)),
            )
            .order_by('price_per_night')
        )
        if floor:
            rooms = rooms.filter(floor=floor)
        if max_price is not None:
            rooms = rooms.filter(price_per_night__lte=max_price)

        for room in rooms:
            room.is_free = room.pk not in busy_ids
            room.stay_nights = nights
            room.stay_total = room.price_per_night * nights
            results.append(room)

    free_rooms = [room for room in results if room.is_free]

    context = {
        'form': form,
        'results': results,
        'free_rooms': free_rooms,
        'busy_count': len(results) - len(free_rooms),
        'nights': nights,
        'searched': searched,
    }
    return render(request, 'rooms/room_search.html', context)


# 2. Интерактивная схема этажей: видно, какие номера свободны сегодня
def hotel_floors(request):
    today = timezone.localdate()
    floors = Floor.objects.prefetch_related('rooms').all()
    context = {
        'floors': floors,
        'busy_room_ids': _busy_room_ids(today, today + timedelta(days=1)),
        'today': today,
    }
    return render(request, 'rooms/hotel_floors.html', context)


# 3. Детальная страница номера: 3D-тур, бронирование, отзывы
def room_detail(request, pk):
    room = get_object_or_404(Room.objects.select_related('floor'), pk=pk)
    today = timezone.localdate()

    upcoming = list(room.upcoming_bookings())
    reviews = room.reviews.filter(is_published=True).select_related('user')

    context = {
        'room': room,
        'booking_form': BookingForm(room=room, user=request.user, initial={'guests': 2 if room.capacity >= 2 else 1}),
        'review_form': ReviewForm(),
        'reviews': reviews,
        'upcoming': upcoming,
        'is_free_tonight': room.is_free(today, today + timedelta(days=1)),
        'today': today,
    }
    return render(request, 'rooms/room_detail.html', context)


# 4. Отзыв об отеле/номере — по одному на гостя, можно обновить
@login_required
@require_POST
def add_review(request, pk):
    room = get_object_or_404(Room, pk=pk)
    form = ReviewForm(request.POST)
    if form.is_valid():
        Review.objects.update_or_create(
            room=room,
            user=request.user,
            defaults={
                'rating': form.cleaned_data['rating'],
                'comment': form.cleaned_data['comment'],
                'is_published': True,
            },
        )
        messages.success(request, "Спасибо за отзыв!")
    else:
        messages.error(request, "Не удалось сохранить отзыв: заполните оценку и текст.")
    return redirect('rooms:room_detail', pk=room.pk)

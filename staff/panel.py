"""Панель администратора отеля (/admin/) вместо стандартной админки Django."""

from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from bookings.models import Booking
from rooms.models import Amenity, Floor, Review, Room, SeasonalRate

from .decorators import is_hotel_admin
from .panel_forms import (
    AmenityForm, FloorForm, RoomForm, SeasonalRateForm, UserCreateForm, UserEditForm, apply_role,
)
from .reports import analytics
from .views import ACTION_LABELS


def admin_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), reverse('accounts:staff_login'))
        if not is_hotel_admin(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


def superuser_required(view):
    @admin_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


def old_login(request):
    """/admin/login/ ведёт на вход для персонала, сохраняя безопасный ?next."""
    target = request.GET.get('next', '')
    if not url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        target = reverse('panel:home')
    if is_hotel_admin(request.user):
        return redirect(target)
    return redirect_to_login(target, reverse('accounts:staff_login'))


# ------------------------------------------------------------------ обзор и брони
@admin_required
def home(request):
    today = timezone.localdate()
    month = analytics(today - timedelta(days=29), 30)
    tonight = analytics(today, 1)
    housekeeping = dict(Room.objects.values_list('housekeeping').annotate(n=Count('pk')).order_by())
    return render(request, 'panel/home.html', {
        'section': 'home',
        'today': today,
        'kpis': [
            ("Загрузка сегодня", f"{tonight['occupancy']}%"),
            ("Выручка за 30 ночей", f"${month['revenue']:.0f}"),
            ("Новые заявки", Booking.objects.filter(status=Booking.STATUS_PENDING).count()),
            ("Заезды сегодня", Booking.objects.filter(
                check_in=today, status__in=(Booking.STATUS_PENDING, Booking.STATUS_CONFIRMED)).count()),
            ("Номеров", Room.objects.count()),
            ("Пользователей", User.objects.count()),
        ],
        'daily': month['daily'],
        'recent': Booking.objects.select_related('room').order_by('-created_at')[:8],
        'housekeeping': [(label, housekeeping.get(key, 0)) for key, label in Room.HOUSEKEEPING_CHOICES],
        'action_labels': ACTION_LABELS,
    })


@admin_required
def bookings(request):
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    items = Booking.objects.select_related('room').order_by('-created_at')
    if query:
        items = items.filter(
            Q(code__icontains=query) | Q(guest_name__icontains=query)
            | Q(guest_email__icontains=query) | Q(guest_phone__icontains=query)
        )
    if status:
        items = items.filter(status=status)
    page = Paginator(items, 20).get_page(request.GET.get('page'))
    for booking in page:
        booking.actions = [(value, ACTION_LABELS[value]) for value in booking.available_statuses]
    return render(request, 'panel/bookings.html', {
        'section': 'bookings', 'page': page, 'q': query, 'status': status,
        'statuses': Booking.STATUS_CHOICES,
    })


# ------------------------------------------------------------------ справочники
def _room_row(room):
    return [room.display_number, room.title, room.floor.number if room.floor else '—',
            f'${room.price_per_night}', room.capacity, room.get_housekeeping_display(),
            'Да' if room.is_active else 'Нет']


# раздел -> настройки таблицы и формы
SECTIONS = {
    'rooms': {
        'title': 'Номера', 'model': Room, 'form': RoomForm,
        'columns': ['Номер', 'Название', 'Этаж', 'Цена', 'Мест', 'Уборка', 'В продаже'],
        'row': _room_row,
        'queryset': lambda: Room.objects.select_related('floor'),
    },
    'floors': {
        'title': 'Этажи', 'model': Floor, 'form': FloorForm,
        'columns': ['Этаж', 'Название', 'Номеров'],
        'row': lambda f: [f.number, f.title, f.rooms.count()],
        'queryset': lambda: Floor.objects.all(),
    },
    'amenities': {
        'title': 'Удобства', 'model': Amenity, 'form': AmenityForm,
        'columns': ['Название', 'Иконка'],
        'row': lambda a: [a.name, a.icon_class or '—'],
        'queryset': lambda: Amenity.objects.all(),
    },
    'rates': {
        'title': 'Сезонные цены', 'model': SeasonalRate, 'form': SeasonalRateForm,
        'columns': ['Номер', 'С', 'По', 'Цена за ночь'],
        'row': lambda r: [str(r.room), f'{r.start_date:%d.%m.%Y}', f'{r.end_date:%d.%m.%Y}',
                          f'${r.price_per_night}'],
        'queryset': lambda: SeasonalRate.objects.select_related('room'),
    },
}


def _section(slug):
    if slug not in SECTIONS:
        raise Http404
    return SECTIONS[slug]


def _delete_blocker(obj):
    """Удаление не должно каскадом стирать брони и номера."""
    if isinstance(obj, Room) and obj.bookings.exists():
        return "У номера есть брони. Вместо удаления снимите отметку «Доступен для бронирования»."
    if isinstance(obj, Floor) and obj.rooms.exists():
        return "На этаже есть номера. Сначала перенесите их на другой этаж."
    return None


@admin_required
def object_list(request, slug):
    config = _section(slug)
    return render(request, 'panel/list.html', {
        'section': slug, 'config': config,
        'rows': [(obj.pk, config['row'](obj)) for obj in config['queryset']()],
    })


@admin_required
def object_edit(request, slug, pk=None):
    config = _section(slug)
    instance = get_object_or_404(config['model'], pk=pk) if pk else None
    form = config['form'](request.POST or None, request.FILES or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Сохранено.")
        return redirect('panel:list', slug=slug)
    return render(request, 'panel/form.html', {
        'section': slug, 'form': form,
        'heading': f"{config['title']}: {'изменить' if pk else 'добавить'}",
        'back_url': reverse('panel:list', args=[slug]),
    })


@admin_required
def object_delete(request, slug, pk):
    config = _section(slug)
    obj = get_object_or_404(config['model'], pk=pk)
    blocker = _delete_blocker(obj)
    if request.method == 'POST' and not blocker:
        obj.delete()
        messages.success(request, "Удалено.")
        return redirect('panel:list', slug=slug)
    return render(request, 'panel/delete.html', {
        'section': slug, 'object': obj, 'blocker': blocker,
        'reviews_lost': obj.reviews.count() if isinstance(obj, Room) else 0,
        'rates_lost': obj.seasonal_rates.count() if isinstance(obj, Room) else 0,
    })


# ------------------------------------------------------------------ отзывы
@admin_required
def reviews(request):
    return render(request, 'panel/reviews.html', {
        'section': 'reviews',
        'page': Paginator(Review.objects.select_related('room', 'user'), 20).get_page(request.GET.get('page')),
    })


@admin_required
@require_POST
def review_toggle(request, pk):
    review = get_object_or_404(Review, pk=pk)
    review.is_published = not review.is_published
    review.save(update_fields=['is_published'])
    messages.success(request, "Отзыв опубликован." if review.is_published else "Отзыв скрыт.")
    return redirect('panel:reviews')


# ------------------------------------------------------------------ пользователи (только суперпользователь)
@superuser_required
def users(request):
    return render(request, 'panel/users.html', {
        'section': 'users',
        'users': User.objects.select_related('staff_profile').order_by('username'),
    })


@superuser_required
def user_edit(request, pk=None):
    instance = get_object_or_404(User, pk=pk) if pk else None
    if instance and instance.is_superuser:
        messages.warning(request, "Суперпользователей изменяют только в резервной админке Django.")
        return redirect('panel:users')
    form_class = UserEditForm if instance else UserCreateForm
    form = form_class(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        apply_role(user, form.cleaned_data['role'])
        messages.success(request, f"Пользователь {user.username} сохранён.")
        return redirect('panel:users')
    return render(request, 'panel/form.html', {
        'section': 'users', 'form': form,
        'heading': f"Пользователь {instance.username}" if instance else "Новый пользователь",
        'back_url': reverse('panel:users'),
    })

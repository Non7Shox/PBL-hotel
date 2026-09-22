"""Проверки доступа к рабочей панели отеля."""

from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from .models import StaffProfile


def is_staff_member(user):
    """Сотрудник — это суперпользователь/админ либо владелец StaffProfile."""
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return StaffProfile.objects.filter(user=user).exists()


def get_staff_profile(user):
    """Профиль сотрудника или None (для админов профиль может отсутствовать)."""
    if not user.is_authenticated:
        return None
    return StaffProfile.objects.filter(user=user).first()


def staff_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.info(request, "Войдите в аккаунт сотрудника, чтобы открыть рабочую панель.")
            return redirect('accounts:login')
        if not is_staff_member(request.user):
            messages.error(request, "Доступ в рабочую панель только для персонала отеля.")
            return redirect('rooms:room_list')
        request.staff_profile = get_staff_profile(request.user)
        return view_func(request, *args, **kwargs)

    return _wrapped


def role_required(*roles):
    """Пускает дальше только сотрудников с указанными ролями (админ проходит всегда)."""

    def decorator(view_func):
        @wraps(view_func)
        @staff_required
        def _wrapped(request, *args, **kwargs):
            profile = getattr(request, 'staff_profile', None)
            if profile is None or profile.role in roles:
                return view_func(request, *args, **kwargs)
            messages.error(request, "У вашей роли нет прав на это действие.")
            return redirect('staff:dashboard')

        return _wrapped

    return decorator

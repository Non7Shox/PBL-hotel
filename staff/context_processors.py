"""Контекст для всех шаблонов: статус сотрудника отеля.

Нужен, чтобы в шапке сайта и внутри страниц показывать ссылки рабочей панели
только персоналу (роли в модели StaffProfile).
"""

from .decorators import get_staff_profile, is_staff_member


def staff_status(request):
    user = getattr(request, 'user', None)
    staff_member = is_staff_member(user) if user else False
    profile = get_staff_profile(user) if staff_member else None
    return {
        'is_staff_member': staff_member,
        'staff_profile': profile,
        'can_manage_bookings': bool(profile and profile.can_manage_bookings) or bool(
            user and user.is_superuser
        ),
    }

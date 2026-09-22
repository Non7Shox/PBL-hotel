from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class StaffProfile(models.Model):
    """Профиль сотрудника отеля.

    Создаётся для тех же пользователей, что и гостевые аккаунты, но даёт доступ
    к рабочей панели: подтверждение броней, заселение, выселение, уборка номеров.
    """

    ROLE_MANAGER = 'manager'
    ROLE_RECEPTIONIST = 'receptionist'
    ROLE_HOUSEKEEPING = 'housekeeping'

    ROLE_CHOICES = [
        (ROLE_MANAGER, 'Менеджер отеля'),
        (ROLE_RECEPTIONIST, 'Администратор стойки'),
        (ROLE_HOUSEKEEPING, 'Служба уборки'),
    ]

    # Роли, которые работают с бронями гостей
    BOOKING_ROLES = (ROLE_MANAGER, ROLE_RECEPTIONIST)

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='staff_profile', verbose_name="Пользователь"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_RECEPTIONIST, verbose_name="Роль")
    phone = models.CharField(max_length=30, blank=True, verbose_name="Рабочий телефон")
    hired_at = models.DateField(default=timezone.localdate, verbose_name="Дата приёма")
    is_on_shift = models.BooleanField(default=True, verbose_name="На смене")
    internal_note = models.TextField(blank=True, verbose_name="Заметка")

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Персонал"
        ordering = ('user__last_name', 'user__first_name')

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} — {self.get_role_display()}"

    @property
    def is_manager(self):
        return self.role == self.ROLE_MANAGER

    @property
    def can_manage_bookings(self):
        return self.role in self.BOOKING_ROLES

    @property
    def can_change_housekeeping(self):
        return self.role in (self.ROLE_MANAGER, self.ROLE_HOUSEKEEPING)

    @property
    def display_name(self):
        return self.user.get_full_name() or self.user.username

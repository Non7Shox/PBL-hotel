import random

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, IntegrityError
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone

from rooms.models import Room

BOOKING_CODE_ALPHABET = 'ACDEFGHJKLMNPQRTUVWXY34679'


def generate_booking_code():
    """Человекочитаемый код брони, например AUR-7K4P2C.

    Не обращается к базе: уникальность обеспечивает unique-констрейнт и
    повтор попытки в Booking.save().
    """
    tail = ''.join(random.choices(BOOKING_CODE_ALPHABET, k=6))
    return f'AUR-{tail}'


class Booking(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CHECKED_IN = 'checked_in'
    STATUS_CHECKED_OUT = 'checked_out'
    STATUS_CANCELLED = 'cancelled'
    STATUS_NO_SHOW = 'no_show'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Ожидает подтверждения'),
        (STATUS_CONFIRMED, 'Подтверждено'),
        (STATUS_CHECKED_IN, 'Гость заселён'),
        (STATUS_CHECKED_OUT, 'Выезд завершён'),
        (STATUS_CANCELLED, 'Отменено'),
        (STATUS_NO_SHOW, 'Гость не приехал'),
    ]

    # Статусы, при которых номер считается занятым
    ACTIVE_STATUSES = (STATUS_PENDING, STATUS_CONFIRMED, STATUS_CHECKED_IN)

    # Какие статусы сотрудник может выставить из текущего
    STAFF_TRANSITIONS = {
        STATUS_PENDING: [STATUS_CONFIRMED, STATUS_CANCELLED, STATUS_NO_SHOW],
        STATUS_CONFIRMED: [STATUS_CHECKED_IN, STATUS_CANCELLED, STATUS_NO_SHOW],
        STATUS_CHECKED_IN: [STATUS_CHECKED_OUT],
        STATUS_CHECKED_OUT: [],
        STATUS_CANCELLED: [],
        STATUS_NO_SHOW: [STATUS_CONFIRMED, STATUS_CANCELLED],
    }

    SOURCE_CHOICES = [
        ('site', 'Онлайн-бронирование'),
        ('desk', 'Стойка регистрации'),
    ]

    code = models.CharField(
        max_length=12,
        unique=True,
        editable=False,
        default=generate_booking_code,
        verbose_name="Код брони",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings',
        verbose_name="Клиент",
    )
    room = models.ForeignKey(
        Room, on_delete=models.CASCADE, related_name='bookings', verbose_name="Номер"
    )
    check_in = models.DateField(verbose_name="Дата заезда")
    check_out = models.DateField(verbose_name="Дата выезда")
    guests = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1)], verbose_name="Количество гостей"
    )

    guest_name = models.CharField(max_length=120, verbose_name="Имя гостя")
    guest_email = models.EmailField(verbose_name="E-mail гостя")
    guest_phone = models.CharField(max_length=30, blank=True, verbose_name="Телефон гостя")
    special_requests = models.TextField(blank=True, verbose_name="Пожелания")

    total_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="Итоговая сумма"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name="Статус"
    )
    source = models.CharField(
        max_length=10, choices=SOURCE_CHOICES, default='site', verbose_name="Источник"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")
    status_changed_at = models.DateTimeField(null=True, blank=True, verbose_name="Статус изменён")

    class Meta:
        verbose_name = "Бронирование"
        verbose_name_plural = "Бронирования"
        ordering = ('-created_at',)
        constraints = [
            models.CheckConstraint(
                condition=Q(check_out__gt=F('check_in')),
                name='booking_check_out_after_check_in',
            ),
        ]
        indexes = [
            models.Index(fields=['room', 'check_in', 'check_out']),
            models.Index(fields=['status']),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_status = self.status

    def __str__(self):
        return f"{self.code} · {self.room.title}"

    # ------------------------------------------------------------------ расчёты
    @property
    def nights(self):
        if not self.check_in or not self.check_out:
            return 0
        return max((self.check_out - self.check_in).days, 0)

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES

    @property
    def is_cancellable(self):
        """Отменить онлайн можно не позже чем за 24 часа до заезда."""
        return (
            self.status in (self.STATUS_PENDING, self.STATUS_CONFIRMED)
            and self.check_in > timezone.localdate()
        )

    @property
    def status_css(self):
        return {
            self.STATUS_PENDING: 'status-pending',
            self.STATUS_CONFIRMED: 'status-confirmed',
            self.STATUS_CHECKED_IN: 'status-in',
            self.STATUS_CHECKED_OUT: 'status-out',
            self.STATUS_CANCELLED: 'status-cancelled',
            self.STATUS_NO_SHOW: 'status-noshow',
        }.get(self.status, 'status-pending')

    @property
    def booked_dates_label(self):
        return f"{self.check_in:%d.%m.%Y} → {self.check_out:%d.%m.%Y}"

    @property
    def available_statuses(self):
        """Статусы, доступные сотруднику из текущего состояния."""
        return self.STAFF_TRANSITIONS.get(self.status, [])

    def recalculate_total(self):
        if self.room_id and self.nights:
            return self.room.price_per_night * self.nights
        return None

    def get_absolute_url(self):
        return reverse('bookings:booking_detail', kwargs={'code': self.code})

    # ------------------------------------------------------------------ валидация
    def clean(self):
        errors = {}
        if self.check_in and self.check_out and self.check_out <= self.check_in:
            errors['check_out'] = "Дата выезда должна быть позже даты заезда."

        if self.check_in and self.check_in < timezone.localdate():
            errors['check_in'] = "Дата заезда не может быть в прошлом."

        if self.room_id and self.guests and self.guests > self.room.capacity:
            errors['guests'] = f"Номер вмещает не более {self.room.capacity} гостей."

        if self.room_id and self.check_in and self.check_out and self.check_out > self.check_in:
            clash = self.overlapping(self.room, self.check_in, self.check_out, exclude_pk=self.pk)
            if clash.exists():
                other = clash.first()
                errors['check_in'] = (
                    f"Номер занят: с {other.check_in:%d.%m.%Y} по {other.check_out:%d.%m.%Y}."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_booking_code()

        # Итоговая сумма всегда считается из тарифа номера и количества ночей
        calculated = self.recalculate_total()
        if calculated is not None:
            self.total_price = calculated

        if self.pk and self._original_status != self.status:
            self.status_changed_at = timezone.now()
            self._original_status = self.status
        elif self.status_changed_at is None:
            self.status_changed_at = timezone.now()

        if self.user_id and not self.guest_email:
            self.guest_email = self.user.email

        # Код генерируется случайно: в редком случае коллизии пробуем ещё раз
        for attempt in range(5):
            try:
                super().save(*args, **kwargs)
                return
            except IntegrityError:
                if attempt == 4 or kwargs.get('update_fields'):
                    raise
                self.code = generate_booking_code()

    # ------------------------------------------------------------------ действия
    def cancel(self):
        self.status = self.STATUS_CANCELLED
        self.save(update_fields=['status', 'status_changed_at', 'updated_at'])

    def set_status(self, new_status):
        """Смена статуса сотрудником с проверкой допустимого перехода."""
        if new_status not in self.available_statuses:
            raise ValidationError(
                f"Из статуса «{self.get_status_display()}» переход невозможен."
            )
        self.status = new_status
        self.save(update_fields=['status', 'status_changed_at', 'updated_at'])

    @classmethod
    def overlapping(cls, room, check_in, check_out, exclude_pk=None):
        """Брони, пересекающиеся с указанным интервалом дат."""
        query = cls.objects.filter(
            room=room,
            status__in=cls.ACTIVE_STATUSES,
            check_in__lt=check_out,
            check_out__gt=check_in,
        )
        if exclude_pk:
            query = query.exclude(pk=exclude_pk)
        return query

    @classmethod
    def is_room_free(cls, room, check_in, check_out, exclude_pk=None):
        return not cls.overlapping(room, check_in, check_out, exclude_pk=exclude_pk).exists()



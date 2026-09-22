from django.contrib.auth.models import User
from django.db import models


class Floor(models.Model):
    number = models.IntegerField(unique=True, verbose_name="Номер этажа")
    title = models.CharField(max_length=100, verbose_name="Название этажа")
    plan_image = models.ImageField(upload_to='floors/', blank=True, null=True, verbose_name="2D-схема этажа")

    class Meta:
        verbose_name = "Этаж"
        verbose_name_plural = "Этажи"
        ordering = ['number']

    def __str__(self):
        return f"{self.number} этаж ({self.title})"


class Room(models.Model):
    HOUSEKEEPING_CHOICES = [
        ('clean', 'Чисто'),
        ('dirty', 'Требует уборки'),
        ('inspected', 'Проверено менеджером'),
        ('out_of_service', 'Вне эксплуатации'),
    ]

    floor = models.ForeignKey(
        Floor,
        on_delete=models.CASCADE,
        related_name='rooms',
        null=True,
        blank=True,
        verbose_name="Этаж"
    )
    room_number = models.CharField(
        max_length=10, blank=True, verbose_name="Номер комнаты", help_text="Например, 201"
    )
    title = models.CharField(max_length=200, verbose_name="Название номера")
    description = models.TextField(verbose_name="Описание")
    image = models.ImageField(upload_to='rooms/', blank=True, null=True, verbose_name="Фото номера")
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена за ночь ($)")
    capacity = models.IntegerField(default=2, verbose_name="Вместимость (чел)")
    homebyme_embed_url = models.URLField(blank=True, null=True, verbose_name="Ссылка на 3D-тур HomeByMe")
    x_pos = models.IntegerField(default=50, verbose_name="Позиция X (%)")
    y_pos = models.IntegerField(default=50, verbose_name="Позиция Y (%)")
    is_active = models.BooleanField(default=True, verbose_name="Доступен для бронирования")
    housekeeping = models.CharField(
        max_length=20, choices=HOUSEKEEPING_CHOICES, default='clean', verbose_name="Статус уборки"
    )

    class Meta:
        verbose_name = "Номер"
        verbose_name_plural = "Номера"
        ordering = ('room_number', 'title')

    def __str__(self):
        return f"{self.display_number} · {self.title}"

    @property
    def display_number(self):
        return self.room_number or f"{self.pk:03d}"

    @property
    def is_bookable(self):
        return self.is_active and self.housekeeping != 'out_of_service'

    @property
    def average_rating(self):
        return self.reviews.filter(is_published=True).aggregate(avg=models.Avg('rating'))['avg']

    @property
    def reviews_count(self):
        return self.reviews.filter(is_published=True).count()

    def is_free(self, check_in, check_out):
        """Свободен ли номер на выбранный период (учитываются активные брони)."""
        from django.apps import apps

        Booking = apps.get_model('bookings', 'Booking')
        return not Booking.overlapping(self, check_in, check_out).exists()

    def upcoming_bookings(self):
        from django.apps import apps
        from django.utils import timezone as tz

        Booking = apps.get_model('bookings', 'Booking')
        return (
            Booking.objects.filter(
                room=self,
                status__in=Booking.ACTIVE_STATUSES,
                check_out__gte=tz.localdate(),
            )
            .select_related('user')
            .order_by('check_in')
        )


class Review(models.Model):
    """Отзыв гостя о номере: одна оценка от одного пользователя на номер."""

    RATING_CHOICES = [(value, f"{value} из 5") for value in range(1, 6)]

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='reviews', verbose_name="Номер")
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='room_reviews', verbose_name="Гость"
    )
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES, verbose_name="Оценка")
    comment = models.TextField(verbose_name="Отзыв")
    is_published = models.BooleanField(default=True, verbose_name="Опубликован")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата отзыва")

    class Meta:
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(fields=('room', 'user'), name='unique_review_per_guest'),
        ]

    def __str__(self):
        return f"{self.room.title} — {self.rating}/5 ({self.user})"

    @property
    def stars(self):
        return range(1, 6)

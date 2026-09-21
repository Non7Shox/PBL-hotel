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
    floor = models.ForeignKey(
        Floor,
        on_delete=models.CASCADE,
        related_name='rooms',
        null=True,
        blank=True,
        verbose_name="Этаж"
    )
    title = models.CharField(max_length=200, verbose_name="Название номера")
    description = models.TextField(verbose_name="Описание")
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена за ночь ($)")
    capacity = models.IntegerField(default=2, verbose_name="Вместимость (чел)")
    homebyme_embed_url = models.URLField(blank=True, null=True, verbose_name="Ссылка на 3D-тур HomeByMe")
    x_pos = models.IntegerField(default=50, verbose_name="Позиция X (%)")
    y_pos = models.IntegerField(default=50, verbose_name="Позиция Y (%)")

    class Meta:
        verbose_name = "Номер"
        verbose_name_plural = "Номера"

    def __str__(self):
        return self.title
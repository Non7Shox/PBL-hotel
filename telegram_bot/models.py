from django.db import models


class DailyDigest(models.Model):
    """Отметка, что утренняя сводка и напоминания за этот день уже разосланы."""

    date = models.DateField(unique=True, verbose_name="Дата")
    sent_at = models.DateTimeField(auto_now_add=True, verbose_name="Отправлено")
    reminders = models.PositiveIntegerField(default=0, verbose_name="Напоминаний гостям")

    class Meta:
        verbose_name = "Утренняя сводка"
        verbose_name_plural = "Утренние сводки"
        ordering = ('-date',)

    def __str__(self):
        return f"Сводка за {self.date:%d.%m.%Y}"

import os

file_path = 'rooms/models.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

seasonal_rate_code = """
class SeasonalRate(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='seasonal_rates', verbose_name="Номер")
    start_date = models.DateField(verbose_name="Начало периода")
    end_date = models.DateField(verbose_name="Конец периода")
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена за ночь ($)")

    class Meta:
        verbose_name = "Сезонная цена"
        verbose_name_plural = "Сезонные цены"
        ordering = ['start_date']

    def __str__(self):
        return f"{self.room.title}: {self.start_date} - {self.end_date} (${self.price_per_night})"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError("Дата начала не может быть позже даты конца.")
"""

# Append to the end of the file
with open(file_path, 'a', encoding='utf-8') as f:
    f.write('\n' + seasonal_rate_code + '\n')
print("added seasonal rate")

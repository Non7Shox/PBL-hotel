from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import Review


class RoomSearchForm(forms.Form):
    """Поиск свободных номеров на главной странице и на странице схемы этажей."""

    check_in = forms.DateField(
        label="Заезд",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    check_out = forms.DateField(
        label="Выезд",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    guests = forms.IntegerField(
        label="Гостей",
        min_value=1,
        max_value=8,
        initial=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 8}),
    )
    floor = forms.ModelChoiceField(
        label="Этаж",
        queryset=None,
        required=False,
        empty_label="Любой этаж",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    max_price = forms.DecimalField(
        label="Цена за ночь до",
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '200'}),
    )

    def __init__(self, *args, **kwargs):
        from .models import Floor

        super().__init__(*args, **kwargs)
        self.fields['floor'].queryset = Floor.objects.order_by('number')
        today = timezone.localdate()
        self.fields['check_in'].widget.attrs['min'] = today.isoformat()
        if not self.is_bound:
            self.initial.setdefault('check_in', today + timedelta(days=1))
            self.initial.setdefault('check_out', today + timedelta(days=3))

    def clean(self):
        cleaned = super().clean()
        check_in = cleaned.get('check_in')
        check_out = cleaned.get('check_out')

        if check_in and check_in < timezone.localdate():
            self.add_error('check_in', "Дата заезда не может быть в прошлом.")

        if check_in and check_out and check_out <= check_in:
            self.add_error('check_out', "Дата выезда должна быть позже даты заезда.")

        return cleaned

    @property
    def nights(self):
        if self.is_valid():
            return (self.cleaned_data['check_out'] - self.cleaned_data['check_in']).days
        return 0


class ReviewForm(forms.ModelForm):
    """Форма отзыва с оценкой от 1 до 5 звёзд."""

    class Meta:
        model = Review
        fields = ('rating', 'comment')
        widgets = {
            'rating': forms.Select(attrs={'class': 'form-select'}),
            'comment': forms.Textarea(
                attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Что понравилось, что стоит улучшить?'}
            ),
        }
        labels = {'rating': "Оценка", 'comment': "Отзыв"}


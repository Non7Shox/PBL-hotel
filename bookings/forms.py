from datetime import timedelta

from django import forms
from django.utils import timezone

from rooms.models import Room

from .models import Booking


class BookingForm(forms.ModelForm):
    """Форма онлайн-бронирования с проверкой дат, гостей и занятости номера."""

    class Meta:
        model = Booking
        fields = (
            'check_in',
            'check_out',
            'guests',
            'guest_name',
            'guest_email',
            'guest_phone',
            'special_requests',
        )
        widgets = {
            'check_in': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'check_out': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'guest_name': forms.TextInput(attrs={'placeholder': 'Иван Петров'}),
            'guest_email': forms.EmailInput(attrs={'placeholder': 'guest@example.com'}),
            'guest_phone': forms.TextInput(attrs={'placeholder': '+998 90 000 00 00'}),
            'special_requests': forms.Textarea(
                attrs={'rows': 3, 'placeholder': 'Ранний заезд, детская кроватка, вид из окна…'}
            ),
        }
        labels = {
            'check_in': "Дата заезда",
            'check_out': "Дата выезда",
            'guests': "Количество гостей",
            'guest_name': "Имя и фамилия",
            'guest_email': "E-mail",
            'guest_phone': "Телефон",
            'special_requests': "Пожелания",
        }

    def __init__(self, *args, room=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.room = room or self.instance.room
        self.user = user if (user and user.is_authenticated) else None

        today = timezone.localdate()
        # Дата заезда — не раньше сегодня, выезд — минимум на следующий день
        self.fields['check_in'].widget.attrs.update({'min': today.isoformat(), 'class': 'form-control'})
        self.fields['check_out'].widget.attrs.update({'class': 'form-control'})

        capacity = self.room.capacity if self.room else 4
        self.fields['guests'] = forms.TypedChoiceField(
            choices=[(n, f"{n} гост.") for n in range(1, capacity + 1)],
            coerce=int,
            initial=self.initial.get('guests') or (self.instance.guests if self.instance.pk else 1),
            label="Количество гостей",
            widget=forms.Select(attrs={'class': 'form-select'}),
        )

        for name, field in self.fields.items():
            if name == 'guests':
                continue
            css = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
            field.widget.attrs.setdefault('class', css)

        if self.instance.pk:
            self.initial.setdefault('check_in', self.instance.check_in)
            self.initial.setdefault('check_out', self.instance.check_out)
        else:
            self.initial.setdefault('check_in', today + timedelta(days=1))
            self.initial.setdefault('check_out', today + timedelta(days=3))

        if self.user and not self.is_bound:
            self.initial.setdefault('guest_name', self.user.get_full_name())
            self.initial.setdefault('guest_email', self.user.email)
            profile = getattr(self.user, 'staff_profile', None)
            if profile and profile.phone:
                self.initial.setdefault('guest_phone', profile.phone)

    def clean(self):
        cleaned = super().clean()
        room = self.room or cleaned.get('room')
        if room is None:
            room = Room.objects.filter(pk=self.data.get('room')).first()
        check_in = cleaned.get('check_in')
        check_out = cleaned.get('check_out')
        guests = cleaned.get('guests')

        if check_in and check_in < timezone.localdate():
            self.add_error('check_in', "Дата заезда не может быть в прошлом.")

        if check_in and check_out and check_out <= check_in:
            self.add_error('check_out', "Дата выезда должна быть позже даты заезда.")

        if room and guests and guests > room.capacity:
            self.add_error('guests', f"Номер вмещает не более {room.capacity} гостей.")

        if room and not room.is_active:
            raise forms.ValidationError("Этот номер временно недоступен для бронирования.")

        if room and check_in and check_out and check_out > check_in:
            clash = Booking.overlapping(room, check_in, check_out, exclude_pk=self.instance.pk)
            if clash.exists():
                other = clash.first()
                self.add_error(
                    'check_in',
                    f"Эти даты уже заняты (бронь {other.code}: "
                    f"{other.check_in:%d.%m.%Y} — {other.check_out:%d.%m.%Y}).",
                )
        return cleaned

    def save(self, commit=True):
        booking = super().save(commit=False)
        if self.room:
            booking.room = self.room
        if self.user:
            booking.user = self.user
        booking.total_price = booking.recalculate_total()
        if commit:
            booking.save()
        return booking


class BookingLookupForm(forms.Form):
    """Поиск брони по коду и e-mail — для гостей без аккаунта."""

    code = forms.CharField(
        max_length=12,
        label="Код брони",
        widget=forms.TextInput(attrs={'placeholder': 'AUR-XXXXXX', 'class': 'form-control'}),
    )
    email = forms.EmailField(
        label="E-mail из брони",
        widget=forms.EmailInput(attrs={'placeholder': 'guest@example.com', 'class': 'form-control'}),
    )

    def clean_code(self):
        return self.cleaned_data['code'].strip().upper()

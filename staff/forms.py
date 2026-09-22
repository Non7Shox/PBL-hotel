from django import forms

from bookings.forms import BookingForm
from rooms.models import Room


class DeskBookingForm(BookingForm):
    """Бронь, которую администратор оформляет на стойке: добавляется выбор номера."""

    room = forms.ModelChoiceField(
        queryset=Room.objects.none(),
        label="Номер",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta(BookingForm.Meta):
        fields = ('room',) + BookingForm.Meta.fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, room=None, **kwargs)
        self.fields['room'].queryset = Room.objects.filter(is_active=True).select_related('floor')
        self.order_fields(
            ['room', 'check_in', 'check_out', 'guests', 'guest_name', 'guest_email', 'guest_phone', 'special_requests']
        )

    def save(self, commit=True):
        booking = super().save(commit=False)
        booking.room = self.cleaned_data['room']
        booking.source = 'desk'
        booking.total_price = booking.recalculate_total()
        if commit:
            booking.save()
        return booking

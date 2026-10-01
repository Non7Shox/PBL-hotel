from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .forms import DeskBookingForm


class DeskBookingTests(TestCase):
    def test_staff_can_open_empty_booking_form(self):
        user = User.objects.create_user(username='reception', is_staff=True)
        self.client.force_login(user)

        response = self.client.get(reverse('staff:desk_booking'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="room"')

    def test_invalid_room_is_reported_as_form_error(self):
        form = DeskBookingForm(data={'room': 'invalid'})

        self.assertFalse(form.is_valid())
        self.assertIn('room', form.errors)

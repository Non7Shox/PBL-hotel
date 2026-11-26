from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Booking
from rooms.models import Amenity, Room

from .models import StaffProfile
from .reports import analytics, occupancy_grid


class FeatureTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.wifi = Amenity.objects.create(name='Wi-Fi')
        self.cheap = Room.objects.create(title='A', description='-', price_per_night=50, capacity=2)
        self.fancy = Room.objects.create(title='B', description='-', price_per_night=200, capacity=4)
        self.fancy.amenities.add(self.wifi)
        self.booking = Booking.objects.create(
            room=self.cheap, check_in=self.today, check_out=self.today + timedelta(days=2),
            guest_name='G', guest_email='g@example.com', status=Booking.STATUS_CONFIRMED,
        )

    def login(self, role):
        user = User.objects.create_user(role, password='test-pass-123')
        StaffProfile.objects.create(user=user, role=role)
        self.client.force_login(user)

    def match(self, **extra):
        start = self.today + timedelta(days=10)
        params = {'check_in': start, 'check_out': start + timedelta(days=1),
                  'guests': 2, 'priority': 'comfort', **extra}
        return self.client.get(reverse('rooms:matchmaker'), params).context['matches']

    def test_matchmaker_ranks_by_wishes_and_price(self):
        self.assertEqual(self.match(wishes=[self.wifi.pk])[0], self.fancy)
        self.assertEqual(self.match(priority='price', max_price=60)[0], self.cheap)

    def test_matchmaker_excludes_busy_rooms(self):
        matches = self.match(check_in=self.today, check_out=self.today + timedelta(days=1))
        self.assertEqual(matches, [self.fancy])

    def test_grid_spans_cover_whole_window(self):
        for row in occupancy_grid(self.today - timedelta(days=1), 7):
            self.assertEqual(sum(cell['span'] for cell in row['cells']), 7)

    def test_analytics_numbers(self):
        data = analytics(self.today, 2)
        self.assertEqual((data['revenue'], data['occupancy'], data['adr']), (100, 50, 50))

    def test_role_access(self):
        urls = [
            reverse('staff:grid'),
            reverse('staff:guest_pass', args=[self.booking.code]),
            reverse('staff:analytics'),
        ]
        expected = {'manager': [200, 200, 200], 'receptionist': [200, 200, 302], 'housekeeping': [302, 302, 302]}
        for role, codes in expected.items():
            self.login(role)
            self.assertEqual([self.client.get(u).status_code for u in urls], codes, role)

    def test_pass_offers_check_in_today(self):
        self.login('receptionist')
        response = self.client.get(reverse('staff:guest_pass', args=[self.booking.code]))
        self.assertTrue(response.context['can_check_in'])

    def test_qr_hidden_from_strangers(self):
        url = reverse('bookings:booking_pass_qr', args=[self.booking.code])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.login('receptionist')
        self.assertEqual(self.client.get(url)['Content-Type'], 'image/svg+xml')

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Booking
from rooms.models import Amenity, Floor, Review, Room, SeasonalRate

from .models import StaffProfile


class AdminPanelTests(TestCase):
    def setUp(self):
        today = timezone.localdate()
        self.floor = Floor.objects.create(number=1, title='F')
        self.room = Room.objects.create(floor=self.floor, title='A', description='-', price_per_night=50)
        self.amenity = Amenity.objects.create(name='Wi-Fi')
        self.rate = SeasonalRate.objects.create(
            room=self.room, start_date=today, end_date=today, price_per_night=70)
        Booking.objects.create(room=self.room, check_in=today, check_out=today + timedelta(days=1),
                               guest_name='G', guest_email='g@example.com')
        self.boss = User.objects.create_superuser('boss', 'b@example.com', None)
        self.guest = User.objects.create_user('guest')
        Review.objects.create(room=self.room, user=self.guest, rating=5, comment='ok')

    def user_with_role(self, role):
        user = User.objects.create_user(role)
        StaffProfile.objects.create(user=user, role=role)
        return user

    def pages(self):
        urls = [reverse('panel:home'), reverse('panel:bookings'), reverse('panel:reviews')]
        for slug, obj in (('rooms', self.room), ('floors', self.floor),
                          ('amenities', self.amenity), ('rates', self.rate)):
            urls += [reverse('panel:list', args=[slug]), reverse('panel:add', args=[slug]),
                     reverse('panel:edit', args=[slug, obj.pk]),
                     reverse('panel:delete', args=[slug, obj.pk])]
        return urls

    def test_admin_url_is_custom_panel(self):
        self.assertEqual(reverse('panel:home'), '/admin/')
        response = self.client.get('/admin/')
        self.assertRedirects(response, '/accounts/staff-login/?next=/admin/', fetch_redirect_response=False)

    def test_old_django_login_url_redirects(self):
        expected = '/accounts/staff-login/?next=/admin/'
        for url in ('/admin/login/?next=/admin/', '/admin/login/',
                    '/admin/login/?next=https://evil.example/'):
            self.assertRedirects(self.client.get(url), expected, fetch_redirect_response=False)
        self.client.force_login(self.boss)
        self.assertRedirects(self.client.get('/admin/login/'), '/admin/')

    def test_superuser_and_manager_open_every_page(self):
        for user in (self.boss, self.user_with_role('manager')):
            self.client.force_login(user)
            for url in self.pages():
                self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_others_are_forbidden(self):
        for user in (self.guest, self.user_with_role('receptionist'), self.user_with_role('housekeeping')):
            self.client.force_login(user)
            for url in self.pages() + [reverse('panel:users')]:
                self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_only_superuser_manages_users(self):
        self.client.force_login(self.user_with_role('manager'))
        self.assertEqual(self.client.get(reverse('panel:users')).status_code, 403)
        self.assertEqual(self.client.post(reverse('panel:user_edit', args=[self.guest.pk]),
                                          {'role': 'manager', 'is_active': 'on'}).status_code, 403)
        self.assertFalse(StaffProfile.objects.filter(user=self.guest).exists())

    def test_superuser_creates_user_and_changes_role(self):
        self.client.force_login(self.boss)
        secret = 'Zx9-long-test-pass'
        self.client.post(reverse('panel:user_add'), {
            'username': 'newbie', 'password1': secret, 'password2': secret, 'role': 'receptionist'})
        user = User.objects.get(username='newbie')
        self.assertEqual(user.staff_profile.role, 'receptionist')
        self.client.post(reverse('panel:user_edit', args=[user.pk]), {'role': '', 'is_active': 'on'})
        self.assertFalse(StaffProfile.objects.filter(user=user).exists())

    def test_create_and_validate(self):
        self.client.force_login(self.boss)
        self.client.post(reverse('panel:add', args=['amenities']), {'name': 'Spa'})
        self.assertTrue(Amenity.objects.filter(name='Spa').exists())
        self.client.post(reverse('panel:add', args=['rooms']), {
            'title': 'Bad', 'description': '-', 'price_per_night': -1, 'capacity': 0,
            'housekeeping': 'clean', 'x_pos': 500, 'y_pos': 1})
        self.assertFalse(Room.objects.filter(title='Bad').exists())

    def test_delete_is_safe(self):
        self.client.force_login(self.boss)
        for slug, obj in (('rooms', self.room), ('floors', self.floor)):
            self.client.post(reverse('panel:delete', args=[slug, obj.pk]))
        self.assertTrue(Room.objects.filter(pk=self.room.pk).exists())
        self.assertTrue(Floor.objects.filter(pk=self.floor.pk).exists())
        url = reverse('panel:delete', args=['amenities', self.amenity.pk])
        self.client.get(url)
        self.assertTrue(Amenity.objects.exists())
        self.client.post(url)
        self.assertFalse(Amenity.objects.exists())

    def test_review_toggle_needs_post(self):
        self.client.force_login(self.boss)
        review = Review.objects.get()
        url = reverse('panel:review_toggle', args=[review.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        review.refresh_from_db()
        self.assertFalse(review.is_published)

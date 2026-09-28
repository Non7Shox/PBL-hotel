from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from staff.models import StaffProfile


class AccountsAuthTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.guest_user = User.objects.create_user(
            username='guest1',
            email='guest1@example.com',
            password='guestpassword123',
            first_name='Guest',
            last_name='User'
        )
        self.staff_user = User.objects.create_user(
            username='staff1',
            email='staff1@example.com',
            password='staffpassword123',
            first_name='Staff',
            last_name='Member'
        )
        self.staff_profile = StaffProfile.objects.create(
            user=self.staff_user,
            role='receptionist',
            phone='+998901234567'
        )
        self.admin_user = User.objects.create_superuser(
            username='admin1',
            email='admin1@example.com',
            password='adminpassword123'
        )

    def test_guest_login_page_renders(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Вход для гостей")
        self.assertContains(response, reverse('accounts:staff_login'))

    def test_staff_login_page_renders(self):
        response = self.client.get(reverse('accounts:staff_login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Портал персонала и управления")

    def test_guest_login_redirects_to_bookings(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'guest1',
            'password': 'guestpassword123'
        }, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('bookings:my_bookings'))

    def test_staff_login_smart_redirect(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'staff1',
            'password': 'staffpassword123'
        }, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('staff:dashboard'))

    def test_admin_login_smart_redirect(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'admin1',
            'password': 'adminpassword123'
        }, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('staff:dashboard'))

    def test_staff_portal_blocks_regular_guest(self):
        response = self.client.post(reverse('accounts:staff_login'), {
            'username': 'guest1',
            'password': 'guestpassword123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Данная учетная запись не имеет прав доступа персонала")

    def test_staff_portal_accepts_staff_member(self):
        response = self.client.post(reverse('accounts:staff_login'), {
            'username': 'staff1',
            'password': 'staffpassword123'
        }, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('staff:dashboard'))

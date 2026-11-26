import json
import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from accounts import views as account_views
from bookings.models import Booking
from rooms.models import Floor, Room
from staff.models import StaffProfile
from . import otp as otp_module
from .models import OTPChallenge, UserProfile
from .otp import OTPError, send_otp, verify_otp


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
        self.assertEqual(response.url, reverse('panel:home'))

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

    def test_email_otp_login_verifies_email_and_signs_user_in(self):
        profile = UserProfile.objects.create(user=self.guest_user)
        OTPChallenge.objects.create(
            identifier=self.guest_user.email,
            purpose='login',
            code_hash=make_password('123456'),
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        response = self.client.post(reverse('accounts:otp_verify'), {
            'purpose': 'login',
            'identifier': self.guest_user.email,
            'code': '123456',
        })

        profile.refresh_from_db()
        self.assertEqual(
            response.url,
            reverse('bookings:my_bookings'),
            [str(message) for message in response.wsgi_request._messages],
        )
        self.assertTrue(profile.email_verified)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.guest_user.pk)

    def test_otp_wrong_attempt_is_counted_and_code_is_one_time(self):
        challenge = OTPChallenge.objects.create(
            identifier='guest@example.com',
            purpose='login',
            code_hash=make_password('123456'),
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        with self.assertRaises(OTPError):
            verify_otp('guest@example.com', 'login', '000000')
        challenge.refresh_from_db()
        self.assertEqual(challenge.attempts, 1)

        verify_otp('guest@example.com', 'login', '123456')
        challenge.refresh_from_db()
        self.assertIsNotNone(challenge.consumed_at)
        with self.assertRaises(OTPError):
            verify_otp('guest@example.com', 'login', '123456')

    def test_registration_requires_email_otp_confirmation(self):
        with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            response = self.client.post(reverse('accounts:signup'), {
                'username': 'newguest',
                'first_name': 'New',
                'last_name': 'Guest',
                'email': 'newguest@example.com',
                'phone': '+998901112233',
                'password1': 'Safe-password-456',
                'password2': 'Safe-password-456',
            })
        self.assertRedirects(response, reverse('accounts:signup'))
        user = User.objects.get(username='newguest')
        self.assertFalse(user.is_active)
        code = re.findall(r'\b\d{6}\b', mail.outbox[-1].body)[0]

        response = self.client.post(reverse('accounts:otp_verify'), {
            'purpose': 'signup',
            'identifier': user.email,
            'code': code,
        })

        user.refresh_from_db()
        profile = UserProfile.objects.get(user=user)
        self.assertRedirects(response, reverse('bookings:my_bookings'))
        self.assertTrue(user.is_active)
        self.assertTrue(profile.email_verified)
        self.assertEqual(profile.phone, '+998901112233')
        self.assertFalse(profile.phone_verified)

    def test_authenticated_guest_can_verify_phone_with_otp(self):
        profile = UserProfile.objects.create(user=self.guest_user)
        OTPChallenge.objects.create(
            identifier='+998901234567',
            purpose='phone',
            code_hash=make_password('654321'),
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        self.client.force_login(self.guest_user)
        session = self.client.session
        session['pending_phone'] = '+998901234567'
        session.save()

        response = self.client.post(reverse('accounts:otp_verify'), {
            'purpose': 'phone',
            'identifier': '+998 90 123 45 67',
            'code': '654321',
        })

        profile.refresh_from_db()
        self.assertRedirects(response, reverse('accounts:profile'))
        self.assertEqual(profile.phone, '+998901234567')
        self.assertTrue(profile.phone_verified)

    def test_otp_resend_cooldown_and_attempt_limit_are_enforced(self):
        with self.settings(
            EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
            OTP_RESEND_COOLDOWN_SECONDS=60,
            OTP_MAX_ATTEMPTS=2,
        ), patch.object(otp_module.secrets, 'randbelow', return_value=123456):
            challenge = send_otp('cooldown@example.com', 'login')
            with self.assertRaises(OTPError):
                send_otp('cooldown@example.com', 'login')

            with self.assertRaises(OTPError):
                verify_otp('cooldown@example.com', 'login', '000000')
            challenge.refresh_from_db()
            with self.assertRaises(OTPError):
                verify_otp('cooldown@example.com', 'login', '000000')
            challenge.refresh_from_db()
            self.assertEqual(challenge.attempts, 2)

    def test_google_callback_links_verified_guest_account(self):
        class FakeResponse:
            def __init__(self, data):
                self.data = json.dumps(data).encode('utf-8')

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def read(self):
                return self.data

        floor = Floor.objects.create(number=1, title='Первый этаж')
        room = Room.objects.create(
            floor=floor,
            room_number='101',
            title='Номер для OAuth теста',
            description='Проверка связывания гостевой брони.',
            price_per_night=100,
            capacity=2,
        )
        booking = Booking.objects.create(
            room=room,
            guest_name='Guest User',
            guest_email=self.guest_user.email,
            check_in=timezone.localdate() + timedelta(days=3),
            check_out=timezone.localdate() + timedelta(days=4),
            guests=1,
        )

        session = self.client.session
        session['google_oauth_state'] = 'expected-state'
        session.save()
        with self.settings(
            GOOGLE_OAUTH_CLIENT_ID='client-id',
            GOOGLE_OAUTH_CLIENT_SECRET='client-secret',
            SITE_URL='https://bookbreinhotel.me',
        ), patch.object(
            account_views.urllib.request,
            'urlopen',
            side_effect=[
                FakeResponse({'access_token': 'access-token'}),
                FakeResponse({
                    'email': self.guest_user.email,
                    'email_verified': True,
                    'given_name': 'Guest',
                    'family_name': 'User',
                }),
            ],
        ):
            response = self.client.get(reverse('accounts:google_callback'), {
                'state': 'expected-state',
                'code': 'oauth-code',
            })

        self.assertEqual(
            response.url,
            reverse('bookings:my_bookings'),
            [str(message) for message in response.wsgi_request._messages],
        )
        profile = UserProfile.objects.get(user=self.guest_user)
        self.assertTrue(profile.email_verified)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.guest_user.pk)
        booking.refresh_from_db()
        self.assertEqual(booking.user, self.guest_user)

    def test_google_callback_rejects_invalid_state(self):
        session = self.client.session
        session['google_oauth_state'] = 'expected-state'
        session.save()
        with patch.object(account_views.urllib.request, 'urlopen') as urlopen:
            response = self.client.get(reverse('accounts:google_callback'), {
                'state': 'wrong-state',
                'code': 'oauth-code',
            })
        self.assertRedirects(response, reverse('accounts:login'))
        urlopen.assert_not_called()

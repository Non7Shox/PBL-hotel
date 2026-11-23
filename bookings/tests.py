import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from pathlib import Path

from rooms.models import Floor, Room, SeasonalRate
from .models import Booking

# Загрузки в тестах пишутся во временную папку, а не в настоящий media/
TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix='pbl_hotel_test_media_')


def tearDownModule():
    shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class BookingViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.floor = Floor.objects.create(number=1, title="Первый этаж")
        self.room = Room.objects.create(
            floor=self.floor,
            room_number="101",
            title="Делюкс с видом",
            description="Просторный номер с 3D-туром.",
            price_per_night=120.00,
            capacity=2,
            model_3d=SimpleUploadedFile("lux.glb", b"glb content", content_type="model/gltf-binary"),
        )
        today = timezone.localdate()
        self.booking = Booking.objects.create(
            room=self.room,
            guest_name="Иван Иванов",
            guest_email="ivan@example.com",
            guest_phone="+998901234567",
            check_in=today + timedelta(days=2),
            check_out=today + timedelta(days=5),
            guests=2,
            status=Booking.STATUS_CONFIRMED,
        )

    def test_booking_create_page(self):
        response = self.client.get(reverse('bookings:booking_create', kwargs={'pk': self.room.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.room.title)

    def test_booking_detail_page(self):
        session = self.client.session
        session['booking_codes'] = [self.booking.code]
        session.save()
        response = self.client.get(reverse('bookings:booking_detail', kwargs={'code': self.booking.code}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.booking.code)
        self.assertContains(response, reverse('rooms:room_detail', kwargs={'pk': self.room.pk}))


class BookingTestMixin:
    def setUp(self):
        self.client = Client()
        self.floor = Floor.objects.create(number=1, title="Первый этаж")
        self.room = Room.objects.create(
            floor=self.floor,
            room_number="101",
            title="Стандарт",
            description="Номер для тестов.",
            price_per_night=Decimal('100.00'),
            capacity=2,
        )
        self.today = timezone.localdate()

    def make_booking(self, start_offset=2, nights=3, **kwargs):
        data = {
            'room': self.room,
            'guest_name': "Иван Иванов",
            'guest_email': "ivan@example.com",
            'check_in': self.today + timedelta(days=start_offset),
            'check_out': self.today + timedelta(days=start_offset + nights),
            'guests': 2,
        }
        data.update(kwargs)
        return Booking.objects.create(**data)

    def unsaved_booking(self, start_offset, nights, **kwargs):
        data = {
            'room': self.room,
            'guest_name': "Гость",
            'guest_email': "guest@example.com",
            'check_in': self.today + timedelta(days=start_offset),
            'check_out': self.today + timedelta(days=start_offset + nights),
        }
        data.update(kwargs)
        return Booking(**data)


class BookingModelTests(BookingTestMixin, TestCase):
    def test_code_is_generated_in_readable_format(self):
        booking = self.make_booking()
        self.assertRegex(booking.code, r'^AUR-[A-Z0-9]{6}$')

    def test_total_price_is_calculated_on_save(self):
        booking = self.make_booking(nights=3)
        self.assertEqual(booking.nights, 3)
        self.assertEqual(booking.total_price, Decimal('300.00'))

    def test_total_price_uses_seasonal_rates(self):
        check_in = self.today + timedelta(days=10)
        SeasonalRate.objects.create(
            room=self.room,
            start_date=check_in,
            end_date=check_in,
            price_per_night=Decimal('180.00'),
        )
        booking = self.make_booking(start_offset=10, nights=2)
        self.assertEqual(booking.total_price, Decimal('280.00'))

    def test_clean_rejects_check_out_before_check_in(self):
        booking = self.unsaved_booking(start_offset=5, nights=-2)
        with self.assertRaises(ValidationError) as ctx:
            booking.clean()
        self.assertIn('check_out', ctx.exception.message_dict)

    def test_clean_rejects_dates_in_the_past(self):
        booking = self.unsaved_booking(start_offset=-1, nights=2)
        with self.assertRaises(ValidationError) as ctx:
            booking.clean()
        self.assertIn('check_in', ctx.exception.message_dict)

    def test_clean_rejects_too_many_guests(self):
        booking = self.unsaved_booking(start_offset=1, nights=1, guests=self.room.capacity + 1)
        with self.assertRaises(ValidationError) as ctx:
            booking.clean()
        self.assertIn('guests', ctx.exception.message_dict)

    def test_overlapping_booking_is_rejected(self):
        self.make_booking(start_offset=2, nights=3)
        clash = self.unsaved_booking(start_offset=4, nights=2)
        with self.assertRaises(ValidationError):
            clash.clean()

    def test_back_to_back_bookings_do_not_overlap(self):
        # Выезд одного гостя и заезд другого в один день — допустимо
        self.make_booking(start_offset=2, nights=3)
        self.assertTrue(Booking.is_room_free(
            self.room, self.today + timedelta(days=5), self.today + timedelta(days=7)
        ))

    def test_cancelled_booking_frees_the_room(self):
        booking = self.make_booking(start_offset=2, nights=3)
        booking.status = Booking.STATUS_CANCELLED
        booking.save()
        self.assertTrue(Booking.is_room_free(self.room, booking.check_in, booking.check_out))


class AvailabilityApiTests(BookingTestMixin, TestCase):
    def get(self, check_in_offset, check_out_offset):
        return self.client.get(reverse('bookings:availability_api'), {
            'room': self.room.pk,
            'check_in': (self.today + timedelta(days=check_in_offset)).isoformat(),
            'check_out': (self.today + timedelta(days=check_out_offset)).isoformat(),
        })

    def test_missing_params_return_400(self):
        response = self.client.get(reverse('bookings:availability_api'), {'room': self.room.pk})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'missing_params')

    def test_bad_date_returns_400(self):
        response = self.client.get(reverse('bookings:availability_api'), {
            'room': self.room.pk, 'check_in': 'not-a-date', 'check_out': '2030-01-01',
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'bad_date')

    def test_free_room_reports_price_and_availability(self):
        data = self.get(1, 3).json()
        self.assertTrue(data['available'])
        self.assertEqual(data['nights'], 2)
        self.assertEqual(data['total'], 200.0)

    def test_booked_room_is_reported_unavailable(self):
        self.make_booking(start_offset=1, nights=3)
        self.assertFalse(self.get(2, 3).json()['available'])

    def test_reversed_dates_are_not_available(self):
        data = self.get(3, 1).json()
        self.assertFalse(data['available'])
        self.assertEqual(data['nights'], 0)


class BookingFlowTests(BookingTestMixin, TestCase):
    def post_booking(self, **overrides):
        data = {
            'check_in': (self.today + timedelta(days=1)).isoformat(),
            'check_out': (self.today + timedelta(days=3)).isoformat(),
            'guests': 1,
            'guest_name': "Тестовый Гость",
            'guest_email': "guest@example.com",
            'guest_phone': "+998901234567",
        }
        data.update(overrides)
        return self.client.post(
            reverse('bookings:booking_create', kwargs={'pk': self.room.pk}), data
        )

    def test_guest_can_book_a_free_room(self):
        response = self.post_booking()
        booking = Booking.objects.get()
        self.assertRedirects(
            response, reverse('bookings:booking_payment', kwargs={'code': booking.code})
        )
        self.assertEqual(booking.status, Booking.STATUS_PENDING)
        self.assertEqual(booking.total_price, Decimal('200.00'))

    def test_booking_payment_step_is_available_to_the_booking_owner(self):
        response = self.post_booking()
        booking = Booking.objects.get()
        self.assertRedirects(
            response,
            reverse('bookings:booking_payment', kwargs={'code': booking.code}),
        )
        response = self.client.get(
            reverse('bookings:booking_payment', kwargs={'code': booking.code})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Все сценарии учебные')

    def test_booking_success_does_not_disclose_unknown_booking(self):
        booking = self.make_booking()
        response = Client().get(
            reverse('bookings:booking_success', kwargs={'code': booking.code})
        )
        self.assertEqual(response.status_code, 404)

    def test_guest_sees_own_booking_after_creating_it(self):
        self.post_booking()
        booking = Booking.objects.get()
        response = self.client.get(reverse('bookings:booking_detail', kwargs={'code': booking.code}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, booking.code)

    def test_stranger_cannot_open_someone_elses_booking(self):
        booking = self.make_booking()
        response = Client().get(reverse('bookings:booking_detail', kwargs={'code': booking.code}))
        self.assertRedirects(response, reverse('bookings:booking_lookup'))

    def test_double_booking_is_refused(self):
        self.make_booking(start_offset=1, nights=2)
        response = self.post_booking()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Booking.objects.count(), 1)
        self.assertTrue(response.context['form'].errors)

    def test_inactive_room_cannot_be_booked(self):
        self.room.is_active = False
        self.room.save()
        response = self.post_booking()
        self.assertRedirects(response, reverse('rooms:room_detail', kwargs={'pk': self.room.pk}))
        self.assertFalse(Booking.objects.exists())

    @override_settings(PAYMENT_GATEWAY='simulation', PAYMENT_SIMULATION_ENABLED=True)
    def test_simulated_payment_marks_booking_as_paid(self):
        booking = self.make_booking()
        session = self.client.session
        session['booking_codes'] = [booking.code]
        session.save()

        response = self.client.post(
            reverse('bookings:payment_process', kwargs={'code': booking.code}),
            {'action': 'success'},
        )

        booking.refresh_from_db()
        self.assertRedirects(
            response,
            reverse('bookings:booking_success', kwargs={'code': booking.code}),
        )
        self.assertEqual(booking.payment_status, Booking.PAYMENT_PAID)
        self.assertTrue(booking.is_paid)
        self.assertTrue(booking.payment_id.startswith('SANDBOX-GATEWAY-'))
        self.assertEqual(booking.payment_method, Booking.PAYMENT_METHOD_TEST_GATEWAY)
        self.assertEqual(booking.payment_amount, booking.total_price)

    @override_settings(PAYMENT_GATEWAY='simulation', PAYMENT_SIMULATION_ENABLED=True)
    def test_apple_pay_sandbox_persists_each_payment_outcome(self):
        for offset, action, expected_status in (
            (2, 'success', Booking.PAYMENT_PAID),
            (10, 'fail', Booking.PAYMENT_FAILED),
            (18, 'cancel', Booking.PAYMENT_CANCELLED),
        ):
            booking = self.make_booking(start_offset=offset)
            session = self.client.session
            session['booking_codes'] = [booking.code]
            session.save()

            response = self.client.post(
                reverse('bookings:payment_process', kwargs={'code': booking.code}),
                {'action': action, 'payment_method': Booking.PAYMENT_METHOD_APPLE_PAY},
            )

            booking.refresh_from_db()
            self.assertRedirects(
                response,
                reverse('bookings:booking_success', kwargs={'code': booking.code}),
            )
            self.assertEqual(booking.payment_status, expected_status)
            self.assertEqual(booking.payment_method, Booking.PAYMENT_METHOD_APPLE_PAY)
            self.assertEqual(booking.payment_amount, booking.total_price)
            self.assertEqual(booking.is_paid, action == 'success')
            if action == 'cancel':
                self.assertIsNone(booking.payment_id)
            else:
                self.assertTrue(booking.payment_id.startswith('SANDBOX-APPLE-'))

    @override_settings(PAYMENT_GATEWAY='simulation', PAYMENT_SIMULATION_ENABLED=True)
    def test_mobile_sandbox_test_card_choice_is_persisted(self):
        booking = self.make_booking()
        session = self.client.session
        session['booking_codes'] = [booking.code]
        session.save()

        self.client.post(
            reverse('bookings:payment_process', kwargs={'code': booking.code}),
            {'action': 'success', 'payment_method': Booking.PAYMENT_METHOD_CARD},
        )

        booking.refresh_from_db()
        self.assertEqual(booking.payment_method, Booking.PAYMENT_METHOD_CARD)
        self.assertEqual(booking.payment_status, Booking.PAYMENT_PAID)
        self.assertTrue(booking.is_paid)
        self.assertTrue(booking.payment_id.startswith('SANDBOX-CARD-'))

    def test_payment_page_offers_separate_card_and_apple_pay_sandbox_choices(self):
        booking = self.make_booking()
        session = self.client.session
        session['booking_codes'] = [booking.code]
        session.save()

        response = self.client.get(
            reverse('bookings:booking_payment', kwargs={'code': booking.code})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Банковская карта (тест)')
        self.assertContains(response, 'Apple Pay (sandbox)')
        self.assertContains(response, 'apple-pay-sandbox-panel')
        self.assertContains(response, 'реального платёжного шлюза нет')

    def test_payment_page_contains_mobile_apple_pay_sandbox_confirmation_steps(self):
        booking = self.make_booking()
        session = self.client.session
        session['booking_codes'] = [booking.code]
        session.save()

        response = self.client.get(
            reverse('bookings:booking_payment', kwargs={'code': booking.code}),
            HTTP_USER_AGENT='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)',
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="iphone-sandbox"')
        self.assertContains(response, 'id="iphone-review-step"')
        self.assertContains(response, 'id="iphone-confirm-step"')
        self.assertContains(response, 'id="iphone-outcomes"')
        self.assertContains(response, 'id="iphone-payment-method"')
        self.assertContains(response, 'Банковская карта (тест)')
        self.assertContains(response, 'реальные средства не списываются')
        self.assertContains(response, 'window.matchMedia')
        self.assertContains(response, 'Подтвердить в sandbox')
        self.assertContains(response, 'Проверяем учебное подтверждение')
        self.assertContains(response, 'name="action" value="success"')
        self.assertContains(response, 'name="action" value="fail"')
        self.assertContains(response, 'name="action" value="cancel"')

    def test_payment_method_and_status_are_shown_on_booking_detail_and_success(self):
        booking = self.make_booking(
            payment_method=Booking.PAYMENT_METHOD_APPLE_PAY,
            payment_status=Booking.PAYMENT_PAID,
            payment_amount=Decimal('300.00'),
            payment_id='SANDBOX-APPLE-demo',
            is_paid=True,
        )
        session = self.client.session
        session['booking_codes'] = [booking.code]
        session.save()

        detail = self.client.get(
            reverse('bookings:booking_detail', kwargs={'code': booking.code})
        )
        success = self.client.get(
            reverse('bookings:booking_success', kwargs={'code': booking.code})
        )

        self.assertContains(detail, 'Apple Pay')
        self.assertContains(detail, 'Оплачено')
        self.assertContains(success, 'SANDBOX-APPLE-demo')
        self.assertContains(success, 'Apple Pay')

    def test_my_bookings_lists_payment_method_and_status(self):
        user = get_user_model().objects.create_user(
            username='applepay-guest',
            email='applepay@example.com',
            password='safe-test-password',
        )
        self.make_booking(
            user=user,
            payment_method=Booking.PAYMENT_METHOD_APPLE_PAY,
            payment_status=Booking.PAYMENT_FAILED,
            payment_amount=Decimal('300.00'),
        )
        self.client.force_login(user)

        response = self.client.get(reverse('bookings:my_bookings'))

        self.assertContains(response, 'Apple Pay')
        self.assertContains(response, 'Ошибка оплаты')

    @override_settings(PAYMENT_GATEWAY='simulation', PAYMENT_SIMULATION_ENABLED=True)
    def test_failed_or_cancelled_payment_does_not_mark_booking_as_paid(self):
        for offset, action, expected_status in (
            (2, 'fail', Booking.PAYMENT_FAILED),
            (10, 'cancel', Booking.PAYMENT_CANCELLED),
        ):
            booking = self.make_booking(start_offset=offset)
            session = self.client.session
            session['booking_codes'] = [booking.code]
            session.save()

            self.client.post(
                reverse('bookings:payment_process', kwargs={'code': booking.code}),
                {'action': action},
            )

            booking.refresh_from_db()
            self.assertEqual(booking.payment_status, expected_status)
            self.assertFalse(booking.is_paid)
            self.assertEqual(booking.payment_method, Booking.PAYMENT_METHOD_TEST_GATEWAY)
            self.assertEqual(booking.payment_amount, booking.total_price)

    @override_settings(PAYMENT_GATEWAY='simulation', PAYMENT_SIMULATION_ENABLED=False)
    def test_simulation_cannot_mark_booking_paid_when_disabled(self):
        booking = self.make_booking()
        session = self.client.session
        session['booking_codes'] = [booking.code]
        session.save()

        self.client.post(
            reverse('bookings:payment_process', kwargs={'code': booking.code}),
            {'action': 'success'},
        )

        booking.refresh_from_db()
        self.assertEqual(booking.payment_status, Booking.PAYMENT_UNPAID)
        self.assertFalse(booking.is_paid)


class ApplePayDomainAssociationTests(TestCase):
    def test_configured_association_file_is_served(self):
        with tempfile.TemporaryDirectory() as directory:
            association_path = Path(directory) / 'apple-association'
            association_path.write_bytes(b'verified-domain-payload')
            with self.settings(APPLE_PAY_DOMAIN_ASSOCIATION_PATH=str(association_path)):
                response = self.client.get(
                    '/.well-known/apple-developer-merchantid-domain-association'
                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'verified-domain-payload')
        self.assertEqual(response['Content-Type'], 'application/octet-stream')

    def test_missing_association_file_returns_404(self):
        with tempfile.TemporaryDirectory() as directory:
            missing_path = Path(directory) / 'not-installed'
            with self.settings(APPLE_PAY_DOMAIN_ASSOCIATION_PATH=str(missing_path)):
                response = self.client.get(
                    '/.well-known/apple-developer-merchantid-domain-association'
                )
        self.assertEqual(response.status_code, 404)

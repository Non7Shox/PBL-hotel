from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from bookings.models import Booking
from rooms.models import Floor, Room

from . import daily, guest, staff
from .handlers import handle_update
from .models import DailyDigest

STAFF_CHAT = -1001234567890
GUEST_CHAT = 555


class FakeAPI:
    """Подменяет Telegram: запоминает отправленные сообщения."""

    def __init__(self):
        self.sent, self.edited, self.answers = [], [], []

    def send_message(self, chat_id, text, keyboard=None):
        self.sent.append({'chat_id': chat_id, 'text': text, 'keyboard': keyboard})

    def edit_message(self, chat_id, message_id, text, keyboard=None):
        self.edited.append({'chat_id': chat_id, 'message_id': message_id, 'text': text, 'keyboard': keyboard})

    def answer_callback(self, callback_id, text=''):
        self.answers.append(text)

    def texts(self, chat_id):
        return [m['text'] for m in self.sent if m['chat_id'] == chat_id]


@override_settings(
    TELEGRAM_BOT_TOKEN='123:test',
    TELEGRAM_BOT_USERNAME='AurelioTestBot',
    TELEGRAM_STAFF_CHAT_ID=str(STAFF_CHAT),
    TELEGRAM_SEND_SYNC=True,
    SITE_URL='http://127.0.0.1:8001',
)
class BotTestCase(TestCase):
    def setUp(self):
        self.api = FakeAPI()
        patcher = mock.patch('telegram_bot.conf.get_api', return_value=self.api)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.today = timezone.localdate()
        floor = Floor.objects.create(number=1, title="Первый этаж")
        self.room = Room.objects.create(
            floor=floor, room_number='101', title="Стандарт", description="Номер для тестов.",
            price_per_night=Decimal('100.00'), capacity=2,
        )
        self.big_room = Room.objects.create(
            floor=floor, room_number='102', title="Семейный", description="Номер для тестов.",
            price_per_night=Decimal('150.00'), capacity=4,
        )

    def make_booking(self, start=2, nights=2, **kwargs):
        data = dict(
            room=self.room, guest_name="Дилноза <b>Каримова</b>", guest_email="dilnoza@mail.uz",
            check_in=self.today + timedelta(days=start), check_out=self.today + timedelta(days=start + nights),
            guests=2,
        )
        data.update(kwargs)
        return Booking.objects.create(**data)

    def message(self, text, chat_id=GUEST_CHAT, chat_type='private'):
        return {'update_id': 1, 'message': {'message_id': 10, 'text': text, 'chat': {'id': chat_id, 'type': chat_type}}}

    def callback(self, booking, status, chat_id=STAFF_CHAT):
        return {'update_id': 2, 'callback_query': {
            'id': 'cb1', 'data': f"st:{booking.pk}:{status}", 'from': {'id': 7, 'username': 'reception_anna'},
            'message': {'message_id': 99, 'chat': {'id': chat_id, 'type': 'supergroup'}},
        }}


class StaffNotificationTests(BotTestCase):
    def test_new_site_booking_goes_to_staff_chat_with_buttons(self):
        response = self.client.post(reverse('bookings:booking_create', kwargs={'pk': self.room.pk}), {
            'check_in': (self.today + timedelta(days=1)).isoformat(),
            'check_out': (self.today + timedelta(days=3)).isoformat(),
            'guests': 1, 'guest_name': "Тимур Алиев", 'guest_email': 'timur@mail.uz', 'guest_phone': '+998901112233',
        })
        booking = Booking.objects.get()
        self.assertEqual(response.status_code, 302)

        [msg] = [m for m in self.api.sent if m['chat_id'] == STAFF_CHAT]
        self.assertIn(booking.code, msg['text'])
        self.assertIn("$200.00", msg['text'])
        callbacks = [b['callback_data'] for row in msg['keyboard'] for b in row]
        self.assertIn(f"st:{booking.pk}:confirmed", callbacks)
        self.assertIn(f"st:{booking.pk}:cancelled", callbacks)
        self.assertEqual(len(mail.outbox), 2)   # письма по-прежнему уходят

    def test_guest_data_is_html_escaped(self):
        card = staff.booking_card(self.make_booking(), "Новая заявка")
        self.assertIn("&lt;b&gt;Каримова&lt;/b&gt;", card)

    def test_confirm_button_changes_status_and_notifies_guest(self):
        booking = self.make_booking(telegram_chat_id=GUEST_CHAT)
        handle_update(self.api, self.callback(booking, Booking.STATUS_CONFIRMED))

        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_CONFIRMED)
        self.assertIn("@reception_anna", self.api.edited[0]['text'])
        self.assertTrue(any("подтверждена" in t for t in self.api.texts(GUEST_CHAT)))
        self.assertEqual(self.api.texts(STAFF_CHAT), [])   # в чат отдельным сообщением не дублируем

    def test_buttons_from_other_chats_are_ignored(self):
        booking = self.make_booking()
        handle_update(self.api, self.callback(booking, Booking.STATUS_CANCELLED, chat_id=GUEST_CHAT))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_PENDING)
        self.assertIn("только в чате ресепшн", self.api.answers[0])

    def test_invalid_transition_is_refused(self):
        booking = self.make_booking(status=Booking.STATUS_CHECKED_OUT)
        handle_update(self.api, self.callback(booking, Booking.STATUS_CONFIRMED))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_CHECKED_OUT)
        self.assertIn("переход невозможен", self.api.answers[0])

    def test_guest_cancellation_on_site_is_reported_to_staff(self):
        booking = self.make_booking()
        session = self.client.session
        session['booking_codes'] = [booking.code]
        session.save()
        self.client.post(reverse('bookings:booking_cancel', kwargs={'code': booking.code}))
        self.assertTrue(any(booking.code in t and "отменено" in t for t in self.api.texts(STAFF_CHAT)))


class GuestBotTests(BotTestCase):
    def test_signed_start_link_subscribes_chat(self):
        booking = self.make_booking()
        handle_update(self.api, self.message(f"/start {guest.link_payload(booking)}"))
        booking.refresh_from_db()
        self.assertEqual(booking.telegram_chat_id, GUEST_CHAT)

    def test_forged_start_link_is_rejected(self):
        booking = self.make_booking()
        handle_update(self.api, self.message(f"/start {booking.code}_0000000000000000"))
        booking.refresh_from_db()
        self.assertIsNone(booking.telegram_chat_id)
        self.assertIn("устарела", self.api.texts(GUEST_CHAT)[0])

    def test_booking_command_needs_matching_email(self):
        booking = self.make_booking()
        handle_update(self.api, self.message(f"/booking {booking.code} someone@else.uz"))
        booking.refresh_from_db()
        self.assertIsNone(booking.telegram_chat_id)

        handle_update(self.api, self.message(f"/booking {booking.code.lower()} DILNOZA@mail.uz"))
        booking.refresh_from_db()
        self.assertEqual(booking.telegram_chat_id, GUEST_CHAT)

    def test_rooms_command_lists_only_free_rooms_with_stay_price(self):
        start = self.today + timedelta(days=5)
        self.make_booking(start=5, nights=2)   # «Стандарт» занят
        handle_update(self.api, self.message(f"/rooms {start:%d.%m} {start + timedelta(days=2):%d.%m}"))
        text = self.api.texts(GUEST_CHAT)[0]
        self.assertNotIn("Стандарт", text)
        self.assertIn("Семейный", text)
        self.assertIn("$300.00", text)

    def test_rooms_command_respects_guest_count(self):
        handle_update(self.api, self.message(f"/rooms {self.today:%d.%m} {self.today + timedelta(days=1):%d.%m} 3"))
        text = self.api.texts(GUEST_CHAT)[0]
        self.assertIn("Семейный", text)
        self.assertNotIn("Стандарт", text)

    def test_stop_unsubscribes(self):
        booking = self.make_booking(telegram_chat_id=GUEST_CHAT)
        handle_update(self.api, self.message("/stop"))
        booking.refresh_from_db()
        self.assertIsNone(booking.telegram_chat_id)

    def test_booking_page_shows_telegram_link(self):
        booking = self.make_booking()
        session = self.client.session
        session['booking_codes'] = [booking.code]
        session.save()
        response = self.client.get(reverse('bookings:booking_detail', kwargs={'code': booking.code}))
        self.assertContains(response, f"https://t.me/AurelioTestBot?start={guest.link_payload(booking)}")


class DailyDigestTests(BotTestCase):
    def test_digest_and_reminders_are_sent_once_per_day(self):
        arriving = self.make_booking(start=0, nights=2)
        tomorrow = self.make_booking(
            start=1, nights=1, room=self.big_room, status=Booking.STATUS_CONFIRMED, telegram_chat_id=GUEST_CHAT,
        )

        record = daily.run_daily(self.api, self.today)
        self.assertEqual(record.reminders, 1)
        [digest] = self.api.texts(STAFF_CHAT)
        self.assertIn(arriving.code, digest)
        self.assertIn("Новых заявок ждут ответа: <b>1</b>", digest)
        self.assertIn("Загрузка на ночь: <b>50%</b>", digest)
        self.assertIn("Напоминаем", self.api.texts(GUEST_CHAT)[0])
        tomorrow.refresh_from_db()
        self.assertIsNotNone(tomorrow.reminder_sent_at)

        self.assertIsNone(daily.run_daily(self.api, self.today))   # повторно не шлём
        self.assertEqual(len(self.api.sent), 2)
        self.assertEqual(DailyDigest.objects.count(), 1)

    @override_settings(TELEGRAM_STAFF_CHAT_ID='')
    def test_without_staff_chat_reminders_go_out_but_digest_is_not_marked_sent(self):
        self.make_booking(start=1, nights=1, status=Booking.STATUS_CONFIRMED, telegram_chat_id=GUEST_CHAT)
        self.assertIsNone(daily.run_daily(self.api, self.today))
        self.assertEqual(len(self.api.texts(GUEST_CHAT)), 1)
        self.assertFalse(DailyDigest.objects.exists())
        self.assertTrue(daily.due_now() or timezone.localtime().hour < 8)

    def test_today_command_only_in_staff_chat(self):
        handle_update(self.api, self.message("/today", chat_id=STAFF_CHAT, chat_type='supergroup'))
        self.assertIn("Сводка на", self.api.texts(STAFF_CHAT)[0])
        handle_update(self.api, self.message("/today"))
        self.assertNotIn("Сводка на", self.api.texts(GUEST_CHAT)[0])


@override_settings(TELEGRAM_BOT_TOKEN='')
class DisabledBotTests(TestCase):
    def test_site_works_without_bot(self):
        floor = Floor.objects.create(number=1, title="Этаж")
        room = Room.objects.create(floor=floor, room_number='1', title="Номер", description=".", price_per_night=50, capacity=2)
        with mock.patch('telegram_bot.conf.get_api') as get_api:
            Client().post(reverse('bookings:booking_create', kwargs={'pk': room.pk}), {
                'check_in': (timezone.localdate() + timedelta(days=1)).isoformat(),
                'check_out': (timezone.localdate() + timedelta(days=2)).isoformat(),
                'guests': 1, 'guest_name': "Гость", 'guest_email': 'g@mail.uz',
            })
        self.assertEqual(Booking.objects.count(), 1)
        get_api.assert_not_called()
        self.assertIsNone(guest.telegram_link(Booking.objects.get()))

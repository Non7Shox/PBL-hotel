from datetime import timedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from rooms.models import Floor, Room
from .models import Booking


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

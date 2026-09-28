from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from .models import Floor, Room, Amenity


class RoomViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.floor = Floor.objects.create(number=1, title="Первый этаж")
        self.amenity = Amenity.objects.create(name="Wi-Fi", icon_class="bi bi-wifi")
        self.model_file = SimpleUploadedFile("lux.glb", b"glb content", content_type="model/gltf-binary")
        self.room = Room.objects.create(
            floor=self.floor,
            room_number="101",
            title="Делюкс с видом",
            description="Просторный номер с 3D-туром.",
            price_per_night=120.00,
            capacity=2,
            model_3d=self.model_file,
            x_pos=40,
            y_pos=60,
        )
        self.room.amenities.add(self.amenity)

    def test_room_list_page(self):
        response = self.client.get(reverse('rooms:room_list'))
        self.assertEqual(response.status_code, 200)

    def test_hotel_floors_page(self):
        response = self.client.get(reverse('rooms:hotel_floors'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('rooms:room_detail', kwargs={'pk': self.room.pk}))
        self.assertContains(response, self.room.title)

    def test_room_detail_page(self):
        response = self.client.get(reverse('rooms:room_detail', kwargs={'pk': self.room.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.room.title)
        self.assertContains(response, self.room.model_3d.url)
        self.assertContains(response, "model-viewer")
        self.assertContains(response, "Wi-Fi")
        self.assertContains(response, "3D-Тур")

    def test_room_detail_homebyme(self):
        room_hbm = Room.objects.create(
            floor=self.floor,
            room_number="102",
            title="HomeByMe Номер",
            description="Номер с HomeByMe.",
            price_per_night=100.00,
            capacity=2,
            homebyme_embed_url="https://home.by.me/embed/test123",
        )
        response = self.client.get(reverse('rooms:room_detail', kwargs={'pk': room_hbm.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, room_hbm.homebyme_embed_url)

    def test_room_search_page(self):
        response = self.client.get(reverse('rooms:room_search'))
        self.assertEqual(response.status_code, 200)

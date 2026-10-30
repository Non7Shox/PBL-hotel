import io
import shutil
import tempfile
from datetime import date
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from .models import Floor, Room, Amenity, SeasonalRate

# Загрузки в тестах пишутся во временную папку, а не в настоящий media/
TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix='pbl_hotel_test_media_')


def tearDownModule():
    shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
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
        self.assertContains(response, "Тур в 3D")

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


class SeasonalPricingTests(TestCase):
    def setUp(self):
        self.floor = Floor.objects.create(number=1, title="Первый этаж")
        self.room = Room.objects.create(
            floor=self.floor,
            room_number="101",
            title="Стандарт",
            description="Номер для тестов.",
            price_per_night=Decimal('100.00'),
            capacity=2,
        )

    def test_base_price_without_seasonal_rates(self):
        total = self.room.get_price_for_dates(date(2030, 6, 1), date(2030, 6, 4))
        self.assertEqual(total, Decimal('300.00'))

    def test_seasonal_rate_applies_only_to_covered_nights(self):
        # Сезон покрывает ночи 2 и 3 июня (end_date включительно)
        SeasonalRate.objects.create(
            room=self.room,
            start_date=date(2030, 6, 2),
            end_date=date(2030, 6, 3),
            price_per_night=Decimal('150.00'),
        )
        total = self.room.get_price_for_dates(date(2030, 6, 1), date(2030, 6, 5))
        self.assertEqual(total, Decimal('100.00') + 2 * Decimal('150.00') + Decimal('100.00'))

    def test_zero_or_negative_stay_costs_nothing(self):
        self.assertEqual(self.room.get_price_for_dates(date(2030, 6, 5), date(2030, 6, 5)), 0)
        self.assertEqual(self.room.get_price_for_dates(date(2030, 6, 5), date(2030, 6, 1)), 0)


class SitePagesTests(TestCase):
    def test_home_has_primary_cta_faq_and_tagline(self):
        response = self.client.get(reverse('rooms:room_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Показать свободные номера')
        self.assertContains(response, 'id="faq"')
        self.assertContains(response, '"@type": "FAQPage"')
        self.assertContains(response, 'data-words')

    def test_legal_pages_are_linked_and_render(self):
        home = self.client.get(reverse('rooms:room_list'))
        for name in ('privacy', 'terms'):
            url = reverse(name)
            self.assertContains(home, f'href="{url}"')
            self.assertEqual(self.client.get(url).status_code, 200)

    @override_settings(DEBUG=False)
    def test_unknown_page_uses_branded_404(self):
        response = self.client.get('/no-such-page/')
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'Такой страницы в отеле нет', status_code=404)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class RoomModelGeneratorTests(TestCase):
    def setUp(self):
        self.floor = Floor.objects.create(number=1, title="Первый этаж")

    def make_room(self, number, **kwargs):
        return Room.objects.create(
            floor=self.floor, room_number=number, title=f"Номер {number}",
            description="Номер для тестов.", price_per_night=Decimal('90.00'), capacity=2, **kwargs,
        )

    def test_generated_file_is_valid_glb(self):
        import json
        import struct
        from rooms.room3d import build_room_glb

        data = build_room_glb(variant=1, capacity=2)
        magic, version, total = struct.unpack('<4sII', data[:12])
        self.assertEqual((magic, version, total), (b'glTF', 2, len(data)))
        json_len, json_type = struct.unpack('<I4s', data[12:20])
        self.assertEqual(json_type, b'JSON')
        gltf = json.loads(data[20:20 + json_len])
        bin_len, bin_type = struct.unpack('<I4s', data[20 + json_len:28 + json_len])
        self.assertEqual(bin_type, b'BIN\x00')
        self.assertEqual(bin_len, gltf['buffers'][0]['byteLength'])
        self.assertGreater(len(gltf['meshes']), 10)
        for view in gltf['bufferViews']:
            self.assertLessEqual(view['byteOffset'] + view['byteLength'], bin_len)

    def test_command_fills_only_rooms_without_a_tour(self):
        from django.core.management import call_command

        bare = self.make_room('201')
        with_tour = self.make_room('202', homebyme_embed_url='https://home.by.me/embed/x')
        call_command('generate_room_models', stdout=io.StringIO())

        bare.refresh_from_db()
        with_tour.refresh_from_db()
        self.assertTrue(bare.has_generated_model)
        self.assertFalse(with_tour.model_3d)

        response = self.client.get(reverse('rooms:room_detail', kwargs={'pk': bare.pk}))
        self.assertContains(response, bare.model_3d.url)
        self.assertContains(response, 'min-camera-orbit')

    def test_custom_camera_orbit_overrides_auto_rotate(self):
        room = self.make_room('203', model_3d=SimpleUploadedFile("suite.glb", b"glb", content_type="model/gltf-binary"),
                              model_camera_orbit='90deg 50deg 75%')
        response = self.client.get(reverse('rooms:room_detail', kwargs={'pk': room.pk}))
        self.assertContains(response, 'camera-orbit="90deg 50deg 75%"')
        self.assertNotContains(response, 'auto-rotate')

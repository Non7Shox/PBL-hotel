from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from rooms.models import Room
from rooms.room3d import build_room_glb


class Command(BaseCommand):
    help = (
        "Генерирует простую 3D модель (.glb) для номеров без 3D тура. "
        "Номера с загруженной моделью или ссылкой HomeByMe не трогает, если не указан --force."
    )

    def add_arguments(self, parser):
        parser.add_argument('room_ids', nargs='*', type=int, help="ID номеров; по умолчанию все")
        parser.add_argument(
            '--force', action='store_true',
            help="Перегенерировать модель, даже если у номера уже есть 3D тур",
        )

    def handle(self, *args, room_ids, force, **options):
        rooms = Room.objects.order_by('pk')
        if room_ids:
            rooms = rooms.filter(pk__in=room_ids)
            missing = set(room_ids) - set(rooms.values_list('pk', flat=True))
            if missing:
                raise CommandError(f"Номера не найдены: {', '.join(map(str, sorted(missing)))}")

        created = 0
        for room in rooms:
            if not force and (room.model_3d or room.homebyme_embed_url):
                self.stdout.write(f"  пропуск: {room}: 3D тур уже есть")
                continue

            data = build_room_glb(variant=room.pk - 1, capacity=room.capacity, name=room.title)
            filename = f"room-{room.pk}.glb"
            room.model_3d.save(filename, ContentFile(data), save=False)
            room.save(update_fields=['model_3d'])
            created += 1
            self.stdout.write(self.style.SUCCESS(
                f"  готово: {room}, файл {room.model_3d.name} ({len(data) // 1024} КБ)"
            ))

        self.stdout.write(f"Создано моделей: {created}")

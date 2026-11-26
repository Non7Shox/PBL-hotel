import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from bookings.models import Booking
from rooms.models import Room

DEMO_DOMAIN = '@demo.invalid'
NAMES = [
    'Азиз Каримов', 'Дилноза Юсупова', 'Иван Петров', 'Мадина Алиева', 'John Smith',
    'Тимур Рахимов', 'Анна Ким', 'Maria Garcia', 'Бобур Исмаилов', 'Ольга Соколова',
]


class Command(BaseCommand):
    help = "Создаёт демо-брони для шахматки и аналитики. --clear удаляет только их."

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help="Только удалить демо-брони")

    def handle(self, *args, clear, **options):
        deleted, _ = Booking.objects.filter(guest_email__endswith=DEMO_DOMAIN).delete()
        self.stdout.write(f"Удалено демо-броней: {deleted}")
        if clear:
            return

        rng = random.Random(7)
        today = timezone.localdate()
        end = today + timedelta(days=16)
        created = 0
        for room in Room.objects.filter(is_active=True).order_by('pk'):
            day = today - timedelta(days=14) + timedelta(days=rng.randint(0, 3))
            while day < end:
                check_out = day + timedelta(days=rng.randint(1, 5))
                if not Booking.overlapping(room, day, check_out).exists():
                    if check_out <= today:
                        status = Booking.STATUS_CHECKED_OUT
                    elif day < today:
                        status = Booking.STATUS_CHECKED_IN
                    else:
                        status = rng.choice([Booking.STATUS_CONFIRMED] * 3 + [Booking.STATUS_PENDING])
                    Booking.objects.create(
                        room=room, check_in=day, check_out=check_out,
                        guests=rng.randint(1, room.capacity), guest_name=rng.choice(NAMES),
                        guest_email=f'guest{created}{DEMO_DOMAIN}', status=status,
                    )
                    created += 1
                day = check_out + timedelta(days=rng.randint(0, 3))
        self.stdout.write(self.style.SUCCESS(f"Создано демо-броней: {created}"))

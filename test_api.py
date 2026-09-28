import os
import django

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pbl_hotel.settings')
    django.setup()

    from django.test import Client
    from rooms.models import Room
    from datetime import date, timedelta
    from django.conf import settings
    settings.ALLOWED_HOSTS = ['*']

    room = Room.objects.first()
    if room:
        c = Client()
        today = date.today()
        check_in = today + timedelta(days=1)
        check_out = today + timedelta(days=3)
        response = c.get(f"/bookings/api/availability/?room={room.pk}&check_in={check_in.strftime('%Y-%m-%d')}&check_out={check_out.strftime('%Y-%m-%d')}")
        print("API Status:", response.status_code)
        print("API Content:", response.content)

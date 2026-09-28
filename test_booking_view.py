import os
import django

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pbl_hotel.settings')
    django.setup()

    from django.test import Client
    from rooms.models import Room
    from django.conf import settings
    settings.ALLOWED_HOSTS = ['*']

    room = Room.objects.first()
    if room:
        c = Client()
        try:
            response = c.get(f'/bookings/new/{room.pk}/')
            print("GET Status:", response.status_code)
        except Exception as e:
            import traceback
            print("GET Error:")
            traceback.print_exc()
    else:
        print("No rooms found")

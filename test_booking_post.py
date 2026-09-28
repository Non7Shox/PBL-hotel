import os
import django

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pbl_hotel.settings')
    django.setup()

    from django.test import Client
    from rooms.models import Room
    from django.conf import settings
    from datetime import date, timedelta
    settings.ALLOWED_HOSTS = ['*']

    room = Room.objects.first()
    if room:
        c = Client()
        today = date.today()
        check_in = today + timedelta(days=1)
        check_out = today + timedelta(days=3)
        response = c.post(f'/bookings/new/{room.pk}/', {
            'check_in': check_in.strftime('%Y-%m-%d'),
            'check_out': check_out.strftime('%Y-%m-%d'),
            'guests': 1,
            'guest_name': 'Test',
            'guest_email': 'test@test.com',
            'guest_phone': '123'
        })
        print("POST Status:", response.status_code)
        if response.context and 'form' in response.context:
            print("Form Errors:", response.context['form'].errors)
    else:
        print("No rooms found")

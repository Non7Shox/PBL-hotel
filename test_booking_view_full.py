import os
import django

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pbl_hotel.settings')
    django.setup()

    from django.test import Client
    from rooms.models import Room
    from bookings.models import Booking
    from django.conf import settings
    from datetime import date, timedelta
    settings.ALLOWED_HOSTS = ['*']

    c = Client()
    try:
        booking = Booking.objects.first()
        if booking:
            response = c.get(f'/bookings/{booking.code}/success/')
            print("Success Page GET Status:", response.status_code)
        else:
            print("No bookings found")
    except Exception as e:
        import traceback
        print("Success Page Error:")
        traceback.print_exc()

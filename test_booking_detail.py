import os
import django

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pbl_hotel.settings')
    django.setup()

    from django.test import Client
    from bookings.models import Booking
    from django.conf import settings
    settings.ALLOWED_HOSTS = ['*']

    booking = Booking.objects.last()
    if booking:
        c = Client()
        try:
            response = c.get(f'/bookings/{booking.code}/')
            print("GET Status:", response.status_code)
        except Exception as e:
            import traceback
            print("Detail Page GET Error:")
            traceback.print_exc()
    else:
        print("No bookings found")

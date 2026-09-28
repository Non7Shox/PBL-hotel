import os
import django

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pbl_hotel.settings')
    django.setup()
    from rooms.models import Room
    from bookings.models import Booking
    from datetime import date, timedelta
    from django.conf import settings
    settings.ALLOWED_HOSTS = ['*']

    room = Room.objects.first()
    if room:
        today = date.today()
        check_in = today + timedelta(days=1)
        check_out = today + timedelta(days=2)
        b = Booking(
            room=room, 
            check_in=check_in, 
            check_out=check_out, 
            guest_name="Test", 
            guest_email="test@test.com", 
        )
        b.clean()
        b.save()
        print("Saved code:", b.code)
        print("Dates:", b.check_in, type(b.check_in), b.check_out, type(b.check_out))
    else:
        print("No rooms found")

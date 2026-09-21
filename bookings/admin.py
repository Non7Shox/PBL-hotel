from django.contrib import admin
from .models import Booking

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('room', 'user', 'check_in', 'check_out', 'status')
    list_filter = ('status', 'check_in')
    search_fields = ('user__username', 'room__title')
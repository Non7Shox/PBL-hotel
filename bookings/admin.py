from django.contrib import admin
from django.utils.html import format_html

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'room',
        'guest_name',
        'booked_dates_label',
        'guests',
        'total_price',
        'status_badge',
        'source',
        'created_at',
    )
    list_filter = ('status', 'source', 'check_in', 'room__floor')
    search_fields = ('code', 'guest_name', 'guest_email', 'guest_phone', 'room__title')
    date_hierarchy = 'check_in'
    list_select_related = ('room', 'user')
    readonly_fields = ('code', 'created_at', 'updated_at', 'status_changed_at', 'total_price')
    list_per_page = 25
    actions = ('confirm_bookings', 'cancel_bookings')

    fieldsets = (
        ("Бронь", {'fields': ('code', 'status', 'source', 'room', 'user')}),
        ("Даты и гости", {'fields': ('check_in', 'check_out', 'guests', 'total_price')}),
        ("Гость", {'fields': ('guest_name', 'guest_email', 'guest_phone', 'special_requests')}),
        ("Служебное", {'fields': ('created_at', 'updated_at', 'status_changed_at')}),
    )

    @admin.display(description="Период")
    def booked_dates_label(self, obj):
        return f"{obj.check_in:%d.%m.%Y} → {obj.check_out:%d.%m.%Y} ({obj.nights} н.)"

    @admin.display(description="Статус")
    def status_badge(self, obj):
        colors = {
            'pending': '#b8860b',
            'confirmed': '#1f7a4d',
            'checked_in': '#1d4ed8',
            'checked_out': '#6b7280',
            'cancelled': '#b91c1c',
            'no_show': '#7c3aed',
        }
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>',
            colors.get(obj.status, '#000'),
            obj.get_status_display(),
        )

    @admin.action(description="Подтвердить выбранные брони")
    def confirm_bookings(self, request, queryset):
        updated = 0
        for booking in queryset:
            try:
                booking.set_status(Booking.STATUS_CONFIRMED)
                updated += 1
            except Exception:
                continue
        self.message_user(request, f"Подтверждено броней: {updated}")

    @admin.action(description="Отменить выбранные брони")
    def cancel_bookings(self, request, queryset):
        count = 0
        for booking in queryset.filter(status__in=(Booking.STATUS_PENDING, Booking.STATUS_CONFIRMED)):
            booking.cancel()
            count += 1
        self.message_user(request, f"Отменено броней: {count}")

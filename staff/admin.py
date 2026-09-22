from django.contrib import admin

from .models import StaffProfile


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone', 'is_on_shift', 'hired_at')
    list_editable = ('role', 'is_on_shift')
    list_filter = ('role', 'is_on_shift')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'phone')
    autocomplete_fields = ('user',)
    list_select_related = ('user',)

from django.contrib import admin

from .models import DailyDigest


@admin.register(DailyDigest)
class DailyDigestAdmin(admin.ModelAdmin):
    list_display = ('date', 'sent_at', 'reminders')
    readonly_fields = ('date', 'sent_at', 'reminders')

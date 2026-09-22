from django.contrib import admin
from .models import Room, Floor, Review


@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ('number', 'title', 'plan_image', 'rooms_count')
    ordering = ('number',)

    @admin.display(description="Номеров")
    def rooms_count(self, obj):
        return obj.rooms.count()


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = (
        'display_number',
        'title',
        'floor',
        'price_per_night',
        'capacity',
        'is_active',
        'housekeeping',
        'x_pos',
        'y_pos',
        'has_3d_tour',
    )
    list_editable = ('price_per_night', 'is_active', 'housekeeping', 'x_pos', 'y_pos')
    list_filter = ('floor', 'is_active', 'housekeeping', 'capacity')
    search_fields = ('title', 'room_number', 'description')
    list_per_page = 20

    @admin.display(boolean=True, description="Есть 3D-тур")
    def has_3d_tour(self, obj):
        return bool(obj.homebyme_embed_url)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('room', 'user', 'rating', 'is_published', 'created_at')
    list_filter = ('rating', 'is_published', 'room')
    search_fields = ('room__title', 'user__username', 'comment')
    list_editable = ('is_published',)
    date_hierarchy = 'created_at'

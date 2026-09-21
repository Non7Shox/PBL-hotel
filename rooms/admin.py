from django.contrib import admin
from .models import Room, Floor


@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ('number', 'title', 'plan_image')
    ordering = ('number',)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('title', 'floor', 'price_per_night', 'capacity', 'x_pos', 'y_pos', 'has_3d_tour')
    list_editable = ('x_pos', 'y_pos')
    list_filter = ('floor',)
    search_fields = ('title',)

    @admin.display(boolean=True, description="Есть 3D-тур")
    def has_3d_tour(self, obj):
        return bool(obj.homebyme_embed_url)
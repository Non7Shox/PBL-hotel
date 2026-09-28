file_path = 'rooms/admin.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add SeasonalRate to import
content = content.replace("Review, Amenity", "Review, Amenity, SeasonalRate")

inline_code = """
class SeasonalRateInline(admin.TabularInline):
    model = SeasonalRate
    extra = 1
"""

# Insert inline class
content = content.replace("@admin.register(Room)", inline_code + "\n\n@admin.register(Room)")

# Add to RoomAdmin
content = content.replace("filter_horizontal = ('amenities',)", "filter_horizontal = ('amenities',)\n    inlines = [SeasonalRateInline]")

# Add a separate admin for SeasonalRate
admin_code = """
@admin.register(SeasonalRate)
class SeasonalRateAdmin(admin.ModelAdmin):
    list_display = ('room', 'start_date', 'end_date', 'price_per_night')
    list_filter = ('room',)
"""

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content + "\n" + admin_code)
print("patched admin")

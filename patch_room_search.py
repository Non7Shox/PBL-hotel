import re

file_path = 'rooms/views.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

old_text = "room.stay_total = room.price_per_night * nights"
new_text = "room.stay_total = room.get_price_for_dates(check_in, check_out)"

content = content.replace(old_text, new_text)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("patched room_search")

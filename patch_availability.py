import re

file_path = 'bookings/views.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

old_text = "payload['total'] = round(float(room.price_per_night) * nights, 2)"
new_text = "payload['total'] = round(float(room.get_price_for_dates(check_in, check_out)), 2)"

content = content.replace(old_text, new_text)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("patched availability_api")

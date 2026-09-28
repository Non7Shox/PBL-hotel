import re

file_path = 'bookings/models.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

old_logic = """    def recalculate_total(self):
        if self.room_id and self.nights:
            return self.room.price_per_night * self.nights
        return None"""

new_logic = """    def recalculate_total(self):
        if self.room_id and self.check_in and self.check_out and self.check_out > self.check_in:
            return self.room.get_price_for_dates(self.check_in, self.check_out)
        return None"""

content = content.replace(old_logic, new_logic)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("patched booking model")

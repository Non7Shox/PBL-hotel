import re

file_path = 'bookings/models.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# I want to add `is_paid` and `payment_id` fields to Booking model
# Let's insert them after `total_price`

fields_to_add = """
    is_paid = models.BooleanField(default=False, verbose_name="Оплачено")
    payment_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="ID платежа (Payme/Click/Stripe)")
"""

content = content.replace(
    'total_price = models.DecimalField(',
    fields_to_add + '\n    total_price = models.DecimalField('
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("patched bookings")

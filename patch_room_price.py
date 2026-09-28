import re

file_path = 'rooms/models.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

method_code = """
    def get_price_for_dates(self, check_in, check_out):
        from datetime import timedelta
        
        nights = (check_out - check_in).days
        if nights <= 0:
            return 0
            
        # Get all rates intersecting with the stay
        rates = list(self.seasonal_rates.filter(
            end_date__gte=check_in,
            start_date__lt=check_out
        ))
        
        total = 0
        current_date = check_in
        while current_date < check_out:
            applicable = next((r for r in rates if r.start_date <= current_date <= r.end_date), None)
            if applicable:
                total += applicable.price_per_night
            else:
                total += self.price_per_night
            current_date += timedelta(days=1)
            
        return total
"""

# Insert before `def is_free`
content = content.replace("    def is_free(self, check_in, check_out):", method_code + "\n    def is_free(self, check_in, check_out):")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("patched room model")

import re

file_path = 'templates/rooms/room_detail.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

replacement = """                    <div class="row g-3">
                        {% for amenity in room.amenities.all %}
                        <div class="col-6 col-md-4">
                            <div class="amenity-pill">
                                {% if amenity.icon_class %}<i class="{{ amenity.icon_class }}"></i>{% else %}<i class="bi bi-check-circle"></i>{% endif %}
                                {{ amenity.name }}
                            </div>
                        </div>
                        {% empty %}
                        <div class="col-12"><p class="text-muted mb-0">Удобства уточняются.</p></div>
                        {% endfor %}
                    </div>"""

# Replace the whole <div class="row g-3"> within <div class="tab-pane fade" id="info-pane" role="tabpanel">
content = re.sub(r'<div class="row g-3">.*?</div>\s*</div>\s*</div>\s*</div>', replacement + '\n                </div>\n            </div>\n        </div>', content, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("patched")

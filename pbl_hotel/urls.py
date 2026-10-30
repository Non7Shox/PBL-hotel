from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('bookings/', include('bookings.urls')),
    path('staff/', include('staff.urls')),
    path('privacy/', TemplateView.as_view(template_name='pages/privacy.html'), name='privacy'),
    path('terms/', TemplateView.as_view(template_name='pages/terms.html'), name='terms'),
    path('', include('rooms.urls')),
]

# Раздача медиафайлов (загруженных картинок) при локальном запуске
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
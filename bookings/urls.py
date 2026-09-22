from django.urls import path

from . import views

app_name = 'bookings'

urlpatterns = [
    path('new/<int:pk>/', views.booking_create, name='booking_create'),
    path('mine/', views.my_bookings, name='my_bookings'),
    path('lookup/', views.booking_lookup, name='booking_lookup'),
    path('api/availability/', views.availability_api, name='availability_api'),
    path('<str:code>/', views.booking_detail, name='booking_detail'),
    path('<str:code>/success/', views.booking_success, name='booking_success'),
    path('<str:code>/cancel/', views.booking_cancel, name='booking_cancel'),
]

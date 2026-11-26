from django.urls import path

from . import views

app_name = 'staff'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('grid/', views.grid, name='grid'),
    path('analytics/', views.analytics_view, name='analytics'),
    path('pass/<str:code>/', views.guest_pass, name='guest_pass'),
    path('desk/', views.desk_booking, name='desk_booking'),
    path('rooms/', views.rooms_board, name='rooms_board'),
    path('rooms/<int:pk>/housekeeping/', views.housekeeping_action, name='housekeeping_action'),
    path('bookings/<int:pk>/<str:action>/', views.booking_action, name='booking_action'),
]

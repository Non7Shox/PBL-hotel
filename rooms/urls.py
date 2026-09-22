from django.urls import path
from . import views

app_name = 'rooms'

urlpatterns = [
    path('', views.room_list, name='room_list'),
    path('search/', views.room_search, name='room_search'),
    path('floors/', views.hotel_floors, name='hotel_floors'),
    path('<int:pk>/', views.room_detail, name='room_detail'),
    path('<int:pk>/review/', views.add_review, name='add_review'),
]

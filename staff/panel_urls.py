from django.urls import path

from . import panel

app_name = 'panel'

urlpatterns = [
    path('', panel.home, name='home'),
    # старый адрес входа Django-админки (закладки, история браузера)
    path('login/', panel.old_login, name='old_login'),
    path('bookings/', panel.bookings, name='bookings'),
    path('reviews/', panel.reviews, name='reviews'),
    path('reviews/<int:pk>/toggle/', panel.review_toggle, name='review_toggle'),
    path('users/', panel.users, name='users'),
    path('users/add/', panel.user_edit, name='user_add'),
    path('users/<int:pk>/', panel.user_edit, name='user_edit'),
    path('<slug:slug>/', panel.object_list, name='list'),
    path('<slug:slug>/add/', panel.object_edit, name='add'),
    path('<slug:slug>/<int:pk>/', panel.object_edit, name='edit'),
    path('<slug:slug>/<int:pk>/delete/', panel.object_delete, name='delete'),
]

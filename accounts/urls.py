from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.SmartLoginView.as_view(), name='login'),
    path('staff-login/', views.StaffLoginView.as_view(), name='staff_login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('signup/', views.signup, name='signup'),
    path('profile/', views.profile, name='profile'),
    path('otp/send/', views.otp_send, name='otp_send'),
    path('otp/verify/', views.otp_verify, name='otp_verify'),
    path('google/', views.google_login, name='google_login'),
    path('google/callback/', views.google_callback, name='google_callback'),
]

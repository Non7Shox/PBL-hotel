from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse

from bookings.models import Booking
from staff.decorators import is_staff_member

from .forms import SignUpForm, StaffLoginForm


class SmartLoginView(LoginView):
    """Умный вход для пользователей с автоматической маршрутизацией по ролям."""
    template_name = 'accounts/login.html'

    def get_success_url(self):
        explicit_next = self.get_redirect_url()
        if explicit_next:
            return explicit_next
        if self.request.user.is_superuser:
            return reverse('staff:dashboard')
        if is_staff_member(self.request.user):
            return reverse('staff:dashboard')
        return reverse('bookings:my_bookings')


class StaffLoginView(LoginView):
    """Специализированная точка входа для персонала и администрации."""
    template_name = 'accounts/staff_login.html'
    authentication_form = StaffLoginForm

    def get_success_url(self):
        explicit_next = self.get_redirect_url()
        if explicit_next:
            return explicit_next
        return reverse('staff:dashboard')


def signup(request):
    """Регистрация гостя с немедленным входом в систему."""
    if request.user.is_authenticated:
        return redirect('bookings:my_bookings')

    form = SignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Аккаунт создан. Добро пожаловать в Aurelio Hotel!")
        return redirect('bookings:my_bookings')

    return render(request, 'accounts/signup.html', {'form': form})


@login_required
def profile(request):
    """Личный кабинет гостя: данные аккаунта и статистика по его броням."""
    bookings = Booking.objects.filter(user=request.user).select_related('room', 'room__floor')
    context = {
        'bookings_total': bookings.count(),
        'bookings_active': bookings.filter(status__in=Booking.ACTIVE_STATUSES).count(),
        'bookings_done': bookings.filter(status='checked_out').count(),
        'bookings': bookings[:3],
    }
    return render(request, 'accounts/profile.html', context)

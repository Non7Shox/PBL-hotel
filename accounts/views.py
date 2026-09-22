from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from bookings.models import Booking

from .forms import SignUpForm


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

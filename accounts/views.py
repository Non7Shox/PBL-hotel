import json
import re
import secrets
import smtplib
import urllib.error
import urllib.parse
import urllib.request

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from bookings.models import Booking
from staff.decorators import is_staff_member

from .forms import SignUpForm, StaffLoginForm
from .models import UserProfile
from .otp import OTPError, send_otp, verify_otp


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
    """Регистрация гостя с подтверждением адреса электронной почты."""
    if request.user.is_authenticated:
        return redirect('bookings:my_bookings')

    form = SignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        user.is_active = False
        user.save()
        UserProfile.objects.create(user=user, phone=form.phone)
        request.session['pending_signup_user_id'] = user.pk
        try:
            send_otp(user.email, 'signup')
        except (OTPError, smtplib.SMTPException, OSError, ImproperlyConfigured) as exc:
            messages.error(request, str(exc))
        else:
            messages.info(request, "Введите код из письма, чтобы завершить регистрацию.")
        return redirect('accounts:signup')

    pending_signup = UserProfile.objects.filter(
        user_id=request.session.get('pending_signup_user_id'),
    ).select_related('user').first()
    return render(request, 'accounts/signup.html', {
        'form': form,
        'pending_signup': pending_signup,
    })


def _find_login_user(identifier):
    from django.contrib.auth.models import User

    if '@' in identifier:
        users = User.objects.filter(email__iexact=identifier, is_active=True)
        return users.first() if users.count() == 1 else None
    profile = UserProfile.objects.filter(
        phone=identifier, phone_verified=True, user__is_active=True,
    ).select_related('user').first()
    return profile.user if profile else None


def _normalize_phone(phone):
    normalized = ''.join(
        character for character in phone if character.isdigit() or character == '+'
    )
    return normalized if re.fullmatch(r'\+?[1-9]\d{6,14}', normalized) else ''


@require_POST
def otp_send(request):
    purpose = request.POST.get('purpose', 'login')
    identifier = request.POST.get('identifier', '').strip()
    if purpose == 'phone' or (purpose == 'login' and '@' not in identifier):
        identifier = _normalize_phone(identifier)
        if not identifier:
            messages.error(request, "Введите корректный номер телефона.")
            return redirect('accounts:profile' if purpose == 'phone' else 'accounts:login')
    if purpose not in ('login', 'signup', 'phone') or not identifier:
        messages.error(request, "Проверьте введённые данные.")
        return redirect('accounts:login')

    if purpose == 'signup':
        user_id = request.session.get('pending_signup_user_id')
        pending = UserProfile.objects.filter(user_id=user_id).select_related('user').first()
        if not pending or pending.user.is_active or pending.user.email.lower() != identifier.lower():
            messages.error(request, "Сначала заполните форму регистрации.")
            return redirect('accounts:signup')
    elif purpose == 'phone':
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if UserProfile.objects.filter(phone=identifier).exclude(user=request.user).exists():
            messages.error(request, "Этот номер уже связан с другим аккаунтом.")
            return redirect('accounts:profile')
        request.session['pending_phone'] = identifier
    elif _find_login_user(identifier) is None:
        messages.info(request, "Если аккаунт существует, код будет отправлен.")
        return redirect('accounts:login')

    try:
        send_otp(identifier, purpose)
    except (OTPError, smtplib.SMTPException, OSError, ImproperlyConfigured) as exc:
        messages.error(request, str(exc))
        return redirect('accounts:profile' if purpose == 'phone' else (
            'accounts:signup' if purpose == 'signup' else 'accounts:login'
        ))

    messages.success(request, "Код отправлен. Он действует 10 минут.")
    return redirect('accounts:profile' if purpose == 'phone' else (
        'accounts:signup' if purpose == 'signup' else 'accounts:login'
    ))


@require_POST
def otp_verify(request):
    purpose = request.POST.get('purpose', 'login')
    identifier = request.POST.get('identifier', '').strip()
    if purpose == 'phone' or (purpose == 'login' and '@' not in identifier):
        identifier = _normalize_phone(identifier)
        if not identifier:
            messages.error(request, "Введите корректный номер телефона.")
            return redirect('accounts:profile' if purpose == 'phone' else 'accounts:login')
    code = request.POST.get('code', '').strip()
    if purpose not in ('login', 'signup', 'phone') or not identifier or not code:
        messages.error(request, "Введите номер или e-mail и код.")
        return redirect('accounts:login')

    if purpose == 'signup':
        user_id = request.session.get('pending_signup_user_id')
        profile = UserProfile.objects.filter(
            user_id=user_id, user__email__iexact=identifier, user__is_active=False,
        ).select_related('user').first()
        if profile is None:
            messages.error(request, "Регистрация не найдена. Заполните форму ещё раз.")
            return redirect('accounts:signup')
    elif purpose == 'phone':
        if not request.user.is_authenticated or request.session.get('pending_phone') != identifier:
            messages.error(request, "Запрос подтверждения телефона устарел.")
            return redirect('accounts:profile')
        if UserProfile.objects.filter(phone=identifier).exclude(user=request.user).exists():
            messages.error(request, "Этот номер уже связан с другим аккаунтом.")
            return redirect('accounts:profile')
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
    else:
        user = _find_login_user(identifier)
        if user is None:
            messages.error(request, "Неверный код или аккаунт не найден.")
            return redirect('accounts:login')
        profile, _ = UserProfile.objects.get_or_create(user=user)

    try:
        verify_otp(identifier, purpose, code)
    except OTPError as exc:
        messages.error(request, str(exc))
        return redirect('accounts:profile' if purpose == 'phone' else (
            'accounts:signup' if purpose == 'signup' else 'accounts:login'
        ))

    if purpose == 'signup':
        profile.email_verified = True
        profile.user.is_active = True
        profile.user.save(update_fields=('is_active',))
        profile.save(update_fields=('email_verified',))
        _link_verified_email_bookings(profile.user)
        request.session.pop('pending_signup_user_id', None)
        login(request, profile.user)
        messages.success(request, "Электронная почта подтверждена. Аккаунт создан.")
        return redirect('bookings:my_bookings')
    if purpose == 'phone':
        profile.phone = identifier
        profile.phone_verified = True
        profile.save(update_fields=('phone', 'phone_verified'))
        request.session.pop('pending_phone', None)
        messages.success(request, "Номер телефона подтверждён.")
        return redirect('accounts:profile')

    if '@' in identifier:
        profile.email_verified = True
        profile.save(update_fields=('email_verified',))
        _link_verified_email_bookings(user)
    login(request, user)
    return redirect('bookings:my_bookings')


def _link_verified_email_bookings(user):
    Booking.objects.filter(
        user__isnull=True,
        guest_email__iexact=user.email,
    ).update(user=user)


def google_login(request):
    if not settings.GOOGLE_OAUTH_CLIENT_ID:
        messages.error(request, "Вход через Google пока не настроен.")
        return redirect('accounts:login')
    state = secrets.token_urlsafe(32)
    request.session['google_oauth_state'] = state
    redirect_uri = settings.SITE_URL.rstrip('/') + reverse('accounts:google_callback')
    params = urllib.parse.urlencode({
        'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'prompt': 'select_account',
    })
    return redirect(f'https://accounts.google.com/o/oauth2/v2/auth?{params}')


def google_callback(request):
    expected_state = request.session.pop('google_oauth_state', None)
    if not expected_state or not secrets.compare_digest(
        expected_state, request.GET.get('state', ''),
    ):
        messages.error(request, "Проверка Google OAuth не пройдена. Попробуйте снова.")
        return redirect('accounts:login')
    if request.GET.get('error'):
        messages.error(request, "Вход через Google отменён или не выполнен.")
        return redirect('accounts:login')
    if not settings.GOOGLE_OAUTH_CLIENT_ID or not settings.GOOGLE_OAUTH_CLIENT_SECRET:
        messages.error(request, "Вход через Google пока не настроен.")
        return redirect('accounts:login')

    redirect_uri = settings.SITE_URL.rstrip('/') + reverse('accounts:google_callback')
    token_payload = urllib.parse.urlencode({
        'code': request.GET.get('code', ''),
        'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
        'client_secret': settings.GOOGLE_OAUTH_CLIENT_SECRET,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }).encode('utf-8')
    token_request = urllib.request.Request(
        'https://oauth2.googleapis.com/token',
        data=token_payload,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(token_request, timeout=10) as response:
            access_token = json.loads(response.read().decode('utf-8'))['access_token']
        user_request = urllib.request.Request(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
        )
        user_request.add_header('Authorization', f'Bearer {access_token}')
        with urllib.request.urlopen(user_request, timeout=10) as response:
            identity = json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, KeyError, ValueError) as exc:
        messages.error(request, "Не удалось подтвердить аккаунт Google. Попробуйте снова.")
        return redirect('accounts:login')

    email = identity.get('email', '').strip().lower()
    email_is_verified = identity.get('email_verified', identity.get('verified_email'))
    if not email or email_is_verified is not True:
        messages.error(request, "Google не подтвердил адрес электронной почты.")
        return redirect('accounts:login')

    from django.contrib.auth import get_user_model
    User = get_user_model()
    matching_users = User.objects.filter(email__iexact=email)
    if matching_users.count() > 1:
        messages.error(request, "Не удалось однозначно определить аккаунт. Обратитесь в отель.")
        return redirect('accounts:login')
    user = matching_users.first()
    if user is None:
        username = email.split('@', 1)[0][:120]
        base_username = username
        suffix = 1
        while User.objects.filter(username=username).exists():
            username = f'{base_username[:110]}{suffix}'
            suffix += 1
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=identity.get('given_name', '')[:150],
            last_name=identity.get('family_name', '')[:150],
        )
    if not user.is_active:
        messages.error(request, "Аккаунт не активен. Подтвердите регистрацию по e-mail.")
        return redirect('accounts:login')
    if user.is_staff or user.is_superuser or is_staff_member(user):
        messages.error(request, "Google-вход доступен только для гостевых аккаунтов.")
        return redirect('accounts:login')
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.email_verified = True
    profile.save(update_fields=('email_verified',))
    _link_verified_email_bookings(user)
    login(request, user)
    return redirect('bookings:my_bookings')


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
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    context['account_profile'] = profile
    return render(request, 'accounts/profile.html', context)

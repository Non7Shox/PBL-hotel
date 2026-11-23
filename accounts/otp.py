import json
import logging
import secrets
import smtplib
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import OTPChallenge

logger = logging.getLogger(__name__)


class OTPError(Exception):
    pass


def _validate_provider_url(endpoint):
    parsed = urllib.parse.urlsplit(endpoint)
    if parsed.scheme == 'https':
        return
    if (
        settings.DEBUG
        and parsed.scheme == 'http'
        and parsed.hostname in ('localhost', '127.0.0.1')
    ):
        return
    raise ImproperlyConfigured('Email and SMS provider URLs must use HTTPS.')


def _send_sms(phone, code):
    token = settings.SMS_API_TOKEN
    endpoint = settings.SMS_API_URL
    message = f'Код Aurelio Hotel: {code}. Действует 10 минут.'
    if bool(token) != bool(endpoint):
        raise ImproperlyConfigured('Set both SMS_API_TOKEN and SMS_API_URL.')
    if not token or not endpoint:
        if settings.DEBUG:
            logger.warning('Development OTP for %s: %s', phone, code)
            return
        raise ImproperlyConfigured('SMS_API_TOKEN and SMS_API_URL are required for phone OTP.')
    _validate_provider_url(endpoint)

    payload = json.dumps({'to': phone, 'message': message}).encode('utf-8')
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    request.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if not 200 <= response.status < 300:
                raise OTPError('SMS provider rejected the request.')
    except urllib.error.URLError as exc:
        raise OTPError('Не удалось отправить SMS. Повторите попытку позже.') from exc


def _send_email(email, code):
    if bool(settings.EMAIL_API_TOKEN) != bool(settings.EMAIL_API_URL):
        raise ImproperlyConfigured('Set both EMAIL_API_TOKEN and EMAIL_API_URL.')
    if settings.EMAIL_API_TOKEN and settings.EMAIL_API_URL:
        _validate_provider_url(settings.EMAIL_API_URL)
        payload = json.dumps({
            'to': email,
            'subject': 'Код подтверждения Aurelio Hotel',
            'message': f'Ваш код: {code}. Он действует 10 минут.',
        }).encode('utf-8')
        request = urllib.request.Request(
            settings.EMAIL_API_URL,
            data=payload,
            headers={
                'Authorization': f'Bearer {settings.EMAIL_API_TOKEN}',
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        request.add_header('Authorization', f'Bearer {settings.EMAIL_API_TOKEN}')
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                if not 200 <= response.status < 300:
                    raise OTPError('Email provider rejected the request.')
        except urllib.error.URLError as exc:
            raise OTPError('Не удалось отправить письмо. Повторите попытку позже.') from exc
        return

    sent = send_mail(
        'Код подтверждения Aurelio Hotel',
        f'Ваш код: {code}. Он действует 10 минут.',
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )
    if not sent:
        raise OTPError('Не удалось отправить письмо. Повторите попытку позже.')


def send_otp(identifier, purpose):
    identifier = identifier.strip()
    now = timezone.now()
    cooldown = now - timedelta(seconds=settings.OTP_RESEND_COOLDOWN_SECONDS)
    if OTPChallenge.objects.filter(
        identifier__iexact=identifier,
        purpose=purpose,
        created_at__gte=cooldown,
    ).exists():
        raise OTPError('Подождите перед повторной отправкой кода.')

    code = f'{secrets.randbelow(1_000_000):06d}'
    challenge = OTPChallenge.objects.create(
        identifier=identifier,
        purpose=purpose,
        code_hash=make_password(code),
        expires_at=now + timedelta(seconds=settings.OTP_TTL_SECONDS),
    )
    try:
        if '@' in identifier:
            _send_email(identifier, code)
        else:
            _send_sms(identifier, code)
    except (OTPError, smtplib.SMTPException, OSError, ImproperlyConfigured):
        challenge.delete()
        raise
    return challenge


def verify_otp(identifier, purpose, code):
    invalid_code = False
    with transaction.atomic():
        challenge = (
            OTPChallenge.objects.select_for_update()
            .filter(
                identifier__iexact=identifier.strip(),
                purpose=purpose,
                consumed_at__isnull=True,
                expires_at__gt=timezone.now(),
                attempts__lt=settings.OTP_MAX_ATTEMPTS,
            )
            .order_by('-created_at')
            .first()
        )
        if challenge is None:
            raise OTPError('Код истёк или больше недействителен. Запросите новый.')

        if not check_password(code, challenge.code_hash):
            challenge.attempts += 1
            challenge.save(update_fields=('attempts',))
            invalid_code = True
        else:
            challenge.consumed_at = timezone.now()
            challenge.save(update_fields=('consumed_at',))

    if invalid_code:
        raise OTPError('Неверный код.')
    return challenge

from django.conf import settings
from django.db import models
from django.db.models import Q


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='account_profile',
    )
    phone = models.CharField(max_length=30, blank=True)
    phone_verified = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('phone',),
                condition=Q(phone_verified=True) & ~Q(phone=''),
                name='unique_nonempty_account_phone',
            ),
        ]

    def __str__(self):
        return f'Profile for {self.user}'


class OTPChallenge(models.Model):
    PURPOSE_CHOICES = [
        ('signup', 'Регистрация'),
        ('login', 'Вход'),
        ('phone', 'Подтверждение телефона'),
    ]

    identifier = models.CharField(max_length=254)
    purpose = models.CharField(max_length=12, choices=PURPOSE_CHOICES)
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=('identifier', 'purpose', '-created_at')),
        ]

    def __str__(self):
        return f'{self.purpose} OTP for {self.identifier}'

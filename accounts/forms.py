import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User


class SignUpForm(UserCreationForm):
    """Регистрация гостя: имя, фамилия, e-mail и пароль."""

    first_name = forms.CharField(
        max_length=60, label="Имя", widget=forms.TextInput(attrs={'placeholder': 'Мухаммад'})
    )
    last_name = forms.CharField(
        max_length=60, label="Фамилия", widget=forms.TextInput(attrs={'placeholder': 'Ахмедов'})
    )
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={'placeholder': 'guest@example.com'}),
    )
    phone = forms.CharField(
        label="Телефон",
        required=False,
        max_length=30,
        widget=forms.TextInput(attrs={'placeholder': '+998 90 000 00 00'}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'phone')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = "Логин"
        self.fields['username'].help_text = "Латинские буквы, цифры и символы @/./+/-/_"
        self.fields['password1'].label = "Пароль"
        self.fields['password2'].label = "Повторите пароль"
        for field in self.fields.values():
            css = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
            field.widget.attrs.setdefault('class', css)

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Пользователь с таким e-mail уже зарегистрирован.")
        return email

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        if phone and not re.fullmatch(r'\+?[0-9 ()-]{7,30}', phone):
            raise forms.ValidationError("Введите корректный номер телефона.")
        normalized = ''.join(
            character for character in phone if character.isdigit() or character == '+'
        )
        if normalized and not re.fullmatch(r'\+?[1-9]\d{6,14}', normalized):
            raise forms.ValidationError("Введите корректный номер телефона.")
        return normalized

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        self.phone = self.cleaned_data.get('phone', '')
        if commit:
            user.save()
        return user


class StaffLoginForm(AuthenticationForm):
    """Форма входа специально для персонала с валидацией прав сотрудника."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = "Служебный логин"
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Логин сотрудника или e-mail'
        })
        self.fields['password'].label = "Пароль"
        self.fields['password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': '••••••••'
        })

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        from staff.decorators import is_staff_member
        if not is_staff_member(user):
            raise forms.ValidationError(
                "Данная учетная запись не имеет прав доступа персонала. "
                "Если вы гость, пожалуйста, используйте обычную форму входа для гостей.",
                code='not_staff'
            )

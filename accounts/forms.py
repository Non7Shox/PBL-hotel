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

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')

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

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user

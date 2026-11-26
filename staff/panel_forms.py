from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator

from rooms.models import Amenity, Floor, Room, SeasonalRate

from .models import StaffProfile


class StyledMixin:
    """Навешивает Bootstrap-классы на все поля."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                continue
            widget.attrs['class'] = 'form-select' if isinstance(widget, forms.Select) else 'form-control'


class RoomForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Room
        fields = (
            'room_number', 'title', 'floor', 'price_per_night', 'capacity', 'housekeeping',
            'is_active', 'description', 'amenities', 'image', 'model_3d',
            'model_camera_orbit', 'homebyme_embed_url', 'x_pos', 'y_pos',
        )
        widgets = {
            'amenities': forms.CheckboxSelectMultiple,
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['model_3d'].validators.append(FileExtensionValidator(['glb']))
        for name, low, high in (('price_per_night', 0, None), ('capacity', 1, None),
                                ('x_pos', 0, 100), ('y_pos', 0, 100)):
            self.fields[name].min_value = low
            self.fields[name].widget.attrs['min'] = low
            if high is not None:
                self.fields[name].widget.attrs['max'] = high

    def clean(self):
        data = super().clean()
        if data.get('price_per_night') is not None and data['price_per_night'] < 0:
            self.add_error('price_per_night', "Цена не может быть отрицательной.")
        if data.get('capacity') is not None and data['capacity'] < 1:
            self.add_error('capacity', "Минимум один гость.")
        for name in ('x_pos', 'y_pos'):
            if data.get(name) is not None and not 0 <= data[name] <= 100:
                self.add_error(name, "Значение от 0 до 100.")
        return data


class FloorForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Floor
        fields = ('number', 'title', 'plan_image')


class AmenityForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Amenity
        fields = ('name', 'icon_class')


class SeasonalRateForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = SeasonalRate
        fields = ('room', 'start_date', 'end_date', 'price_per_night')
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'end_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def clean_price_per_night(self):
        price = self.cleaned_data['price_per_night']
        if price < 0:
            raise forms.ValidationError("Цена не может быть отрицательной.")
        return price


ROLE_CHOICES = [('', 'Гость (без доступа персонала)')] + StaffProfile.ROLE_CHOICES


class UserCreateForm(StyledMixin, UserCreationForm):
    role = forms.ChoiceField(label="Роль", choices=ROLE_CHOICES, required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')


class UserEditForm(StyledMixin, forms.ModelForm):
    role = forms.ChoiceField(label="Роль", choices=ROLE_CHOICES, required=False)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'is_active')
        labels = {'is_active': "Аккаунт активен"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        profile = StaffProfile.objects.filter(user=self.instance).first()
        self.fields['role'].initial = profile.role if profile else ''


def apply_role(user, role):
    if role:
        StaffProfile.objects.update_or_create(user=user, defaults={'role': role})
    else:
        StaffProfile.objects.filter(user=user).delete()
        if user.is_staff:
            user.is_staff = False
            user.save(update_fields=['is_staff'])

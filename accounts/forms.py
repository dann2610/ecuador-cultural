from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm, UserCreationForm

from core.forms import BootstrapFormMixin

from .models import User


class SignUpForm(BootstrapFormMixin, UserCreationForm):
    accept_terms = forms.BooleanField(label="Acepto las condiciones de uso y la política de privacidad")

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email"]
        labels = {"username": "Nombre de usuario", "first_name": "Nombres", "last_name": "Apellidos"}

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con este correo.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.TOURIST  # el rol nunca se elige en el registro público
        if commit:
            user.save()
        return user


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    pass


class ResetForm(BootstrapFormMixin, PasswordResetForm):
    pass


class NewPasswordForm(BootstrapFormMixin, SetPasswordForm):
    pass


class ProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone", "bio", "avatar"]
        labels = {"first_name": "Nombres", "last_name": "Apellidos"}

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ese correo ya está en uso.")
        return email

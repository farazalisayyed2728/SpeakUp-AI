from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django import forms
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.contrib.auth.password_validation import validate_password

from .models import User

INPUT_CLASS = (
    "w-full rounded-xl border border-ink/25 bg-white px-4 py-3 text-ink "
    "placeholder:text-ink-soft/60 focus:border-violet focus:outline-none"
)


class Styled:
    """Applies the design-system input classes to every visible widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not field.widget.is_hidden:
                field.widget.attrs["class"] = INPUT_CLASS
            if field.widget.input_type == "password":
                # Alpine toggles show/hide (see templates/accounts/_field.html).
                field.widget.attrs[":type"] = "show ? 'text' : 'password'"


class RegistrationForm(Styled, forms.Form):
    full_name = forms.CharField(
        label="Full name", max_length=150, widget=forms.TextInput(attrs={"autocomplete": "name"})
    )
    email = forms.EmailField(
        label="Email", max_length=254, widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    timezone = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_email(self):
        return User.objects.normalize_email(self.cleaned_data["email"])

    def clean_timezone(self):
        # Detected by the browser; an unknown value just falls back to UTC, never an error.
        value = self.cleaned_data.get("timezone") or "UTC"
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError, OSError):
            return "UTC"
        return value

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "The two passwords don't match.")
        elif p1:
            candidate = User(email=cleaned.get("email", ""), full_name=cleaned.get("full_name", ""))
            try:
                validate_password(p1, candidate)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned


class LoginForm(Styled, forms.Form):
    email = forms.EmailField(
        label="Email", widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def clean_email(self):
        return User.objects.normalize_email(self.cleaned_data["email"])


class EmailForm(Styled, forms.Form):
    email = forms.EmailField(
        label="Email", widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )

    def clean_email(self):
        return User.objects.normalize_email(self.cleaned_data["email"])


class StyledPasswordChangeForm(Styled, PasswordChangeForm):
    pass


class StyledSetPasswordForm(Styled, SetPasswordForm):
    pass

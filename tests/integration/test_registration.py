import pytest
from django.core import mail
from django.urls import reverse

from apps.accounts.models import AuditEvent, User
from apps.profiles.models import UserProfile

pytestmark = pytest.mark.django_db
URL = "accounts:register"
GOOD = {
    "full_name": "Ada Lovelace",
    "email": "Ada@Example.com",
    "password1": "violet-lantern-92",
    "password2": "violet-lantern-92",
    "timezone": "Asia/Kolkata",
}


def post(client, **over):
    return client.post(reverse(URL), {**GOOD, **over})


def test_form_renders_with_password_hints(client):
    r = client.get(reverse(URL))
    assert r.status_code == 200 and b"At least 10 characters" in r.content


def test_valid_registration_creates_user_profile_audit_and_email(client):
    r = post(client)
    assert r.status_code == 302 and r.url == reverse("accounts:check-email")
    u = User.objects.get(email="ada@example.com")
    assert u.is_email_verified is False and u.password.startswith("argon2")
    assert UserProfile.objects.get(user=u).timezone == "Asia/Kolkata"
    assert AuditEvent.objects.filter(user=u, event_type="registered").exists()
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ["ada@example.com"]
    assert "http://testserver/accounts/verify/" in mail.outbox[0].body


def test_unknown_timezone_falls_back_to_utc(client):
    post(client, timezone="Mars/Olympus")
    assert UserProfile.objects.get().timezone == "UTC"


@pytest.mark.parametrize("pw", ["short1", "1234567890123", "password1234", "ada@example.com"])
def test_weak_passwords_rejected(client, pw):
    r = post(client, password1=pw, password2=pw)
    assert r.status_code == 200 and User.objects.count() == 0
    assert b"Please fix the following" in r.content


def test_password_mismatch_rejected(client):
    r = post(client, password2="different-pass-77")
    assert r.status_code == 200 and b"don" in r.content and User.objects.count() == 0


def test_invalid_email_rejected(client):
    assert post(client, email="nope").status_code == 200 and User.objects.count() == 0


def test_duplicate_email_gives_identical_response_and_creates_nothing(client):
    post(client)
    mail.outbox.clear()
    r = post(client, email="ADA@EXAMPLE.COM", full_name="Someone Else")
    assert r.status_code == 302 and r.url == reverse("accounts:check-email")  # same as success
    assert User.objects.count() == 1
    assert len(mail.outbox) == 1 and "already" in mail.outbox[0].subject.lower()
    assert AuditEvent.objects.filter(event_type="register_duplicate").exists()


def test_authenticated_user_is_redirected_away(client, make_user):
    client.force_login(make_user())
    assert client.get(reverse(URL)).status_code == 302

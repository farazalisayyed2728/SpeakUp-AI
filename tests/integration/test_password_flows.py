import pytest
from django.contrib.auth.tokens import PasswordResetTokenGenerator, default_token_generator
from django.core import mail
from django.test import Client
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.accounts import tokens
from apps.accounts.models import AuditEvent, User

pytestmark = pytest.mark.django_db


def forgot(client, email):
    return client.post(reverse("accounts:password-forgot"), {"email": email})


def reset_url(user, token):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    return reverse("accounts:password-reset-confirm", kwargs={"uidb64": uid, "token": token})


def test_reset_request_is_identical_for_known_and_unknown_email(client, make_user):
    make_user()
    a, b = forgot(client, "ada@example.com"), forgot(client, "ghost@example.com")
    assert a.status_code == b.status_code == 302 and a.url == b.url
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ["ada@example.com"]


def test_full_reset_flow_and_link_is_single_use(client, make_user, link_in_last_email):
    u = make_user(verified=False)
    forgot(client, "ada@example.com")
    link = link_in_last_email().replace("http://testserver", "")
    r = client.get(link, follow=True)  # Django swaps the token into the session
    assert r.status_code == 200 and b"Choose a new password" in r.content
    set_url = r.redirect_chain[-1][0]
    r = client.post(
        set_url, {"new_password1": "fresh-garden-lamp-3", "new_password2": "fresh-garden-lamp-3"}
    )
    assert r.status_code == 302 and r.url == reverse("accounts:password-reset-complete")
    u.refresh_from_db()
    assert u.check_password("fresh-garden-lamp-3") and u.is_email_verified
    assert AuditEvent.objects.filter(user=u, event_type="password_reset_completed").exists()
    r2 = client.get(link, follow=True)  # the same link no longer works
    assert b"be used" in r2.content


def test_expired_reset_link_rejected(client, make_user, monkeypatch):
    u = make_user()
    token = default_token_generator.make_token(u)
    real_now = PasswordResetTokenGenerator._now
    monkeypatch.setattr(
        PasswordResetTokenGenerator,
        "_now",
        lambda self: real_now(self).replace(year=real_now(self).year + 1),
    )
    assert b"be used" in client.get(reset_url(u, token), follow=True).content


def test_password_reset_signs_out_other_devices(client, make_user, link_in_last_email):
    make_user()
    other = Client()
    other.post(
        reverse("accounts:login"), {"email": "ada@example.com", "password": "correct-horse-battery"}
    )
    assert other.get(reverse("core:dashboard")).status_code == 200
    forgot(client, "ada@example.com")
    r = client.get(link_in_last_email().replace("http://testserver", ""), follow=True)
    client.post(
        r.redirect_chain[-1][0],
        {"new_password1": "fresh-garden-lamp-3", "new_password2": "fresh-garden-lamp-3"},
    )
    assert other.get(reverse("core:dashboard")).status_code == 302


def test_verification_token_cannot_reset_a_password(client, make_user):
    u = make_user()
    assert (
        b"be used"
        in client.get(reset_url(u, tokens.make_verification_token(u)), follow=True).content
    )


def test_password_change_requires_login(client):
    assert client.get(reverse("accounts:password-change")).status_code == 302


def test_password_change_needs_old_password_and_keeps_session(client, make_user):
    u = make_user()
    client.force_login(u)
    url = reverse("accounts:password-change")
    new = {"new_password1": "fresh-garden-lamp-3", "new_password2": "fresh-garden-lamp-3"}
    assert client.post(url, {"old_password": "nope", **new}).status_code == 200
    u.refresh_from_db()
    assert u.check_password("correct-horse-battery")
    ok = client.post(url, {"old_password": "correct-horse-battery", **new})
    assert ok.status_code == 200 and b"Password changed" in ok.content
    u.refresh_from_db()
    assert u.check_password("fresh-garden-lamp-3")
    assert client.get(reverse("core:dashboard")).status_code == 200  # still signed in here
    assert AuditEvent.objects.filter(event_type="password_changed").exists()


def test_reset_email_task_skips_unknown_user():
    from apps.accounts.tasks import send_password_reset_email

    assert send_password_reset_email.delay(999999).get() == "skipped"
    assert User.objects.count() == 0

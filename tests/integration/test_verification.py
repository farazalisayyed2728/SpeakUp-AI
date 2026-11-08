import pytest
from django.core import mail, signing
from django.urls import reverse

from apps.accounts import tokens
from apps.accounts.models import AuditEvent, User

pytestmark = pytest.mark.django_db


def test_link_verifies_account_once(client, make_user):
    u = make_user(verified=False)
    url = reverse("accounts:verify-email", kwargs={"token": tokens.make_verification_token(u)})
    r = client.get(url)
    assert r.status_code == 200 and b"Email confirmed" in r.content
    u.refresh_from_db()
    first = u.email_verified_at
    assert first is not None
    assert AuditEvent.objects.filter(user=u, event_type="email_verified").count() == 1
    # reuse: friendly message, no state change, no second audit event
    r2 = client.get(url)
    u.refresh_from_db()
    assert b"Already confirmed" in r2.content and u.email_verified_at == first
    assert AuditEvent.objects.filter(event_type="email_verified").count() == 1


def test_expired_link(client, make_user, monkeypatch):
    import time

    u = make_user(verified=False)
    t = tokens.make_verification_token(u)
    real = time.time
    monkeypatch.setattr(signing.time, "time", lambda: real() + 60 * 60 * 25)
    r = client.get(reverse("accounts:verify-email", kwargs={"token": t}))
    assert r.status_code == 400 and b"expired" in r.content
    u.refresh_from_db()
    assert not u.is_email_verified


def test_tampered_link(client, make_user):
    make_user(verified=False)
    r = client.get(reverse("accounts:verify-email", kwargs={"token": "1:abc:garbage"}))
    assert r.status_code == 400 and b"isn" in r.content


def test_unverified_user_cannot_log_in_but_can_resend(client, make_user):
    make_user(verified=False)
    r = client.post(reverse("accounts:login"), {"email": "ada@example.com", "password": "correct-horse-battery"})
    assert r.status_code == 200 and b"confirm your email" in r.content
    assert "_auth_user_id" not in client.session
    client.post(reverse("accounts:resend-verification"), {"email": "ada@example.com"})
    assert len(mail.outbox) == 1


def test_resend_is_silent_for_unknown_and_already_verified(client, make_user):
    make_user(verified=True)
    for email in ("ada@example.com", "ghost@example.com"):
        r = client.post(reverse("accounts:resend-verification"), {"email": email})
        assert r.status_code == 302 and r.url == reverse("accounts:check-email")
    assert mail.outbox == []


def test_verification_email_task_is_idempotent(make_user):
    from django.utils import timezone

    from apps.accounts.tasks import send_verification_email

    u = make_user(verified=False)
    assert send_verification_email.delay(u.pk).get() == "sent"
    u.email_verified_at = timezone.now()
    u.save()
    assert send_verification_email.delay(u.pk).get() == "skipped"
    assert len(mail.outbox) == 1


def test_superuser_is_created_verified():
    assert User.objects.create_superuser("root@example.com", "pw-pw-pw-pw-1").is_email_verified
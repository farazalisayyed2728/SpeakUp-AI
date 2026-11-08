import pytest
from django.core import mail
from django.urls import reverse

from apps.accounts import tasks
from apps.accounts.models import User

pytestmark = pytest.mark.django_db


def test_tasks_have_bounded_retries_and_time_limits():
    for t in (
        tasks.send_verification_email,
        tasks.send_password_reset_email,
        tasks.send_already_registered_email,
    ):
        assert t.max_retries == 5 and t.retry_backoff and t.retry_jitter
        assert t.soft_time_limit < t.time_limit and t.acks_late


def test_registration_still_succeeds_when_broker_is_down(client, monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr(tasks.send_verification_email, "delay", boom)
    r = client.post(
        reverse("accounts:register"),
        {
            "full_name": "A",
            "email": "a@example.com",
            "password1": "violet-lantern-92",
            "password2": "violet-lantern-92",
        },
    )
    assert r.status_code == 302 and User.objects.filter(email="a@example.com").exists()
    assert mail.outbox == []  # user can use "Resend confirmation" later


def test_mail_server_failure_raises_so_celery_can_retry(make_user, monkeypatch, settings):
    from celery.exceptions import Retry

    u = make_user(verified=False)

    def fail(*a, **k):
        raise OSError("smtp down")

    monkeypatch.setattr(tasks, "send_mail", fail)
    settings.CELERY_TASK_EAGER_PROPAGATES = True
    with pytest.raises((Retry, OSError)):
        tasks.send_verification_email.delay(u.pk).get()

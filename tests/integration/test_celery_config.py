from django.conf import settings

from apps.core.tasks import ping
from config import celery_app


def test_ping_task_runs_eagerly():
    assert ping.delay().get() == "pong"


def test_celery_uses_django_settings_and_is_bounded():
    assert celery_app.main == "speakup"
    assert settings.CELERY_TASK_SOFT_TIME_LIMIT < settings.CELERY_TASK_TIME_LIMIT
    assert settings.CELERY_TASK_ACKS_LATE is True
    assert settings.CELERY_ACCEPT_CONTENT == ["json"]


def test_task_registered():
    assert "core.ping" in celery_app.tasks

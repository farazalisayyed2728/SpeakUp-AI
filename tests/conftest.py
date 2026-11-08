import re

import pytest
from django.core import mail


@pytest.fixture(autouse=True)
def _clean_state():
    from django.core.cache import cache

    from apps.core import ratelimit

    cache.clear()
    ratelimit.reset_for_tests()
    yield


@pytest.fixture
def make_user(db):
    from django.utils import timezone

    from apps.accounts.models import User
    from apps.profiles.models import UserProfile

    def _make(email="ada@example.com", password="correct-horse-battery", verified=True, **extra):
        user = User.objects.create_user(
            email, password, email_verified_at=timezone.now() if verified else None, **extra
        )
        UserProfile.objects.create(user=user)
        return user

    return _make


@pytest.fixture
def link_in_last_email():
    def _get() -> str:
        assert mail.outbox, "no email was sent"
        return re.search(r"https?://\S+", mail.outbox[-1].body).group(0)

    return _get
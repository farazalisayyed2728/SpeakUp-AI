import time

import pytest
from django.core import signing

from apps.accounts import tokens

pytestmark = pytest.mark.django_db


def test_roundtrip(make_user):
    u = make_user()
    uid, fp = tokens.read_verification_token(tokens.make_verification_token(u))
    assert uid == u.pk and tokens.email_matches(u, fp)


def test_tampered_token_rejected(make_user):
    t = tokens.make_verification_token(make_user())
    with pytest.raises(signing.BadSignature):
        tokens.read_verification_token(t[:-3] + "xyz")


def test_expired_token_rejected(make_user, monkeypatch):
    t = tokens.make_verification_token(make_user())
    real = time.time
    monkeypatch.setattr(signing.time, "time", lambda: real() + 60 * 60 * 25)
    with pytest.raises(signing.SignatureExpired):
        tokens.read_verification_token(t)


def test_changing_email_invalidates_old_token(make_user):
    u = make_user()
    _, fp = tokens.read_verification_token(tokens.make_verification_token(u))
    u.email = "new@example.com"
    assert not tokens.email_matches(u, fp)


def test_reset_token_cannot_be_used_as_verification_token(make_user):
    from django.contrib.auth.tokens import default_token_generator

    u = make_user()
    with pytest.raises(signing.BadSignature):
        tokens.read_verification_token(default_token_generator.make_token(u))
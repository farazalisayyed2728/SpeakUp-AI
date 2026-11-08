"""Purpose-specific, expiring email-verification tokens.

Signed with a salt unique to this purpose, so a verification token can never be replayed as a
password-reset token (or vice versa). The token embeds a fingerprint of the email address, so
changing the email invalidates old links.
"""

import hashlib

from django.conf import settings
from django.core import signing

_SALT = "accounts.email-verification.v1"


def _signer() -> signing.TimestampSigner:
    return signing.TimestampSigner(salt=_SALT)


def _email_fp(email: str) -> str:
    return hashlib.sha256(email.lower().encode()).hexdigest()[:12]


def make_verification_token(user) -> str:
    return _signer().sign(f"{user.pk}:{_email_fp(user.email)}")


def read_verification_token(token: str) -> tuple[int, str]:
    """Return (user_id, email_fingerprint). Raises SignatureExpired or BadSignature."""
    value = _signer().unsign(token, max_age=settings.EMAIL_VERIFICATION_MAX_AGE)
    uid, fp = value.split(":", 1)
    return int(uid), fp


def email_matches(user, fingerprint: str) -> bool:
    return _email_fp(user.email) == fingerprint
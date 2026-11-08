"""Account business rules. Views stay thin and call into here."""

import enum
import logging

from django.core import signing
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.tasks_util import enqueue
from apps.profiles.models import UserProfile

from . import audit, tasks, tokens
from .models import AuditEvent, User

logger = logging.getLogger(__name__)


class VerifyResult(enum.Enum):
    VERIFIED = "verified"
    ALREADY_VERIFIED = "already_verified"
    EXPIRED = "expired"
    INVALID = "invalid"


def register(*, email: str, full_name: str, password: str, tz: str, request) -> None:
    """Create an account, or quietly handle an existing one.

    The caller always shows the same "check your email" page either way, so the form can't
    be used to discover which emails have accounts.
    """
    email = User.objects.normalize_email(email)
    user = None
    try:
        with transaction.atomic():
            user = User.objects.create_user(email, password, full_name=full_name.strip())
            UserProfile.objects.create(user=user, timezone=tz)
    except IntegrityError:
        user = None  # duplicate (also covers a race between two simultaneous sign-ups)

    if user is not None:
        audit.record(AuditEvent.Type.REGISTERED, request, user)
        enqueue(tasks.send_verification_email, user.pk)  # after commit
        return

    existing = User.objects.filter(email=email).first()
    audit.record(
        AuditEvent.Type.REGISTER_DUPLICATE, request, existing, email=audit.fingerprint(email)
    )
    if existing is not None:
        enqueue(tasks.send_already_registered_email, existing.pk)


def verify_email(token: str, request) -> VerifyResult:
    try:
        uid, fp = tokens.read_verification_token(token)
    except signing.SignatureExpired:
        return VerifyResult.EXPIRED
    except (signing.BadSignature, ValueError):
        return VerifyResult.INVALID

    with transaction.atomic():
        user = User.objects.select_for_update().filter(pk=uid, is_active=True).first()
        if user is None or not tokens.email_matches(user, fp):
            return VerifyResult.INVALID
        if user.is_email_verified:
            return VerifyResult.ALREADY_VERIFIED  # single use: nothing changes the second time
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
    audit.record(AuditEvent.Type.EMAIL_VERIFIED, request, user)
    return VerifyResult.VERIFIED


def resend_verification(email: str, request) -> None:
    email = User.objects.normalize_email(email)
    user = User.objects.filter(email=email, is_active=True).first()
    audit.record(AuditEvent.Type.VERIFICATION_RESENT, request, user, email=audit.fingerprint(email))
    if user is not None and not user.is_email_verified:
        enqueue(tasks.send_verification_email, user.pk)


def request_password_reset(email: str, request) -> None:
    email = User.objects.normalize_email(email)
    user = User.objects.filter(email=email, is_active=True).first()
    audit.record(
        AuditEvent.Type.PASSWORD_RESET_REQUESTED, request, user, email=audit.fingerprint(email)
    )
    if user is not None:
        enqueue(tasks.send_password_reset_email, user.pk)

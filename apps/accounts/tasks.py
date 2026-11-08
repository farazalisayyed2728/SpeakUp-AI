import logging

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import make_verification_token

logger = logging.getLogger(__name__)
User = get_user_model()

# Shared retry policy: transient mail failures retry with exponential backoff + jitter, a
# bounded number of times. Tasks only receive a user id; tokens are minted inside the task
# so secrets never travel through the broker.
RETRY = {
    "autoretry_for": (OSError,),  # includes SMTP/connection errors
    "retry_backoff": True,
    "retry_backoff_max": 300,
    "retry_jitter": True,
    "max_retries": 5,
    "soft_time_limit": 30,
    "time_limit": 45,
    "acks_late": True,
}


def _absolute(path: str) -> str:
    return settings.SITE_URL.rstrip("/") + path


def _send(user, subject: str, template: str, **ctx) -> None:
    body = render_to_string(template, {"user": user, "site_url": settings.SITE_URL, **ctx})
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)


@shared_task(name="accounts.send_verification_email", **RETRY)
def send_verification_email(user_id: int) -> str:
    user = User.objects.filter(pk=user_id, is_active=True).first()
    if user is None or user.is_email_verified:
        return "skipped"  # idempotent: a duplicate delivery after verification is harmless
    link = _absolute(
        reverse("accounts:verify-email", kwargs={"token": make_verification_token(user)})
    )
    _send(user, "Confirm your SpeakUp AI email", "emails/verify.txt", link=link, hours=24)
    return "sent"


@shared_task(name="accounts.send_password_reset_email", **RETRY)
def send_password_reset_email(user_id: int) -> str:
    user = User.objects.filter(pk=user_id, is_active=True).first()
    if user is None or not user.has_usable_password():
        return "skipped"
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = _absolute(
        reverse("accounts:password-reset-confirm", kwargs={"uidb64": uid, "token": token})
    )
    _send(user, "Reset your SpeakUp AI password", "emails/reset.txt", link=link, minutes=60)
    return "sent"


@shared_task(name="accounts.send_already_registered_email", **RETRY)
def send_already_registered_email(user_id: int) -> str:
    user = User.objects.filter(pk=user_id, is_active=True).first()
    if user is None:
        return "skipped"
    _send(
        user,
        "You already have a SpeakUp AI account",
        "emails/already_registered.txt",
        login_url=_absolute(reverse("accounts:login")),
        reset_url=_absolute(reverse("accounts:password-forgot")),
    )
    return "sent"

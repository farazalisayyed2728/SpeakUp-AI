import hashlib
import logging

from apps.core.net import client_ip

from .models import AuditEvent

logger = logging.getLogger(__name__)


def fingerprint(email: str) -> str:
    """Short one-way id so events about unknown emails can be correlated without storing them."""
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()[:16]


def record(event_type: str, request=None, user=None, **metadata) -> None:
    """Write an audit event. Auditing must never break the user's request."""
    try:
        AuditEvent.objects.create(
            user=user if (user is not None and user.pk) else None,
            event_type=event_type,
            ip_address=client_ip(request) if request else None,
            user_agent=(request.META.get("HTTP_USER_AGENT", "")[:200] if request else ""),
            metadata=metadata,
        )
    except Exception:
        logger.exception("Failed to write audit event %s", event_type)

import ipaddress

from django.conf import settings


def client_ip(request) -> str:
    """Best-effort client IP.

    X-Forwarded-For is attacker-controlled unless it was appended by *our* proxy, so we only
    read it when TRUSTED_PROXY_COUNT > 0, and then take the Nth entry from the RIGHT (the one
    our outermost trusted proxy added). Anything to its left is ignored.
    """
    n = settings.TRUSTED_PROXY_COUNT
    if n > 0:
        raw = request.META.get("HTTP_X_FORWARDED_FOR", "")
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        if len(parts) >= n:
            try:
                return str(ipaddress.ip_address(parts[-n]))
            except ValueError:
                pass
    return request.META.get("REMOTE_ADDR") or "0.0.0.0"  # noqa: S104

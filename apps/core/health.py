import logging

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@never_cache
@require_GET
def live(request):
    """Liveness: the process is up. Must not touch dependencies."""
    return JsonResponse({"status": "ok"})


def _check_database() -> bool:
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception:
        logger.exception("readiness: database check failed")
        return False


def _check_cache() -> bool:
    try:
        cache.set("health:ping", "1", timeout=5)
        return cache.get("health:ping") == "1"
    except Exception:
        logger.exception("readiness: cache check failed")
        return False


@never_cache
@require_GET
def ready(request):
    """Readiness: dependencies the web process needs. Returns booleans only — no internals."""
    checks = {"database": _check_database(), "cache": _check_cache()}
    ok = all(checks.values())
    return JsonResponse(
        {"status": "ok" if ok else "unavailable", "checks": checks},
        status=200 if ok else 503,
    )

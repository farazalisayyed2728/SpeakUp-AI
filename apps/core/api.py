"""Consistent error contract for every application-owned API (see Engineering Rules §5)."""

import logging

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .context import request_id_var

logger = logging.getLogger(__name__)

_CODES = {
    status.HTTP_400_BAD_REQUEST: (
        "VALIDATION_ERROR",
        "Please check the highlighted fields.",
        False,
    ),
    status.HTTP_401_UNAUTHORIZED: ("AUTH_REQUIRED", "Please sign in to continue.", False),
    status.HTTP_403_FORBIDDEN: ("PERMISSION_DENIED", "You don't have access to that.", False),
    status.HTTP_404_NOT_FOUND: ("RESOURCE_NOT_FOUND", "We couldn't find that item.", False),
    status.HTTP_405_METHOD_NOT_ALLOWED: (
        "METHOD_NOT_ALLOWED",
        "That action isn't supported.",
        False,
    ),
    status.HTTP_429_TOO_MANY_REQUESTS: (
        "RATE_LIMITED",
        "Too many attempts. Please try again shortly.",
        True,
    ),
}


def error_body(code: str, message: str, retryable: bool, errors=None) -> dict:
    body = {
        "success": False,
        "error_code": code,
        "message": message,
        "retryable": retryable,
        "request_id": request_id_var.get(),
        "data": None,
    }
    if errors is not None:
        body["errors"] = errors  # field-level validation errors
    return body


def exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    response = drf_exception_handler(exc, context)
    if response is None:
        # Unexpected failure: log the details privately, show nothing internal.
        logger.exception("Unhandled API exception")
        return Response(
            error_body(
                "INTERNAL_ERROR", "Something went wrong on our side. Please try again.", True
            ),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    code, message, retryable = _CODES.get(
        response.status_code, ("REQUEST_FAILED", "We couldn't complete that request.", False)
    )
    errors = response.data if response.status_code == status.HTTP_400_BAD_REQUEST else None
    response.data = error_body(code, message, retryable, errors)
    # Only ever expose a real Retry-After (set by DRF throttling) — never invent one.
    return response

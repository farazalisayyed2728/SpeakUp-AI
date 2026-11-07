from django.http import Http404
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

factory = APIRequestFactory()


def make_view(exc):
    class V(APIView):
        permission_classes = [AllowAny]

        def get(self, request):
            raise exc

    return V.as_view()


def call(exc):
    resp = make_view(exc)(factory.get("/x"))
    resp.render()
    return resp


CONTRACT = {"success", "error_code", "message", "retryable", "request_id", "data"}


def test_not_found_contract():
    r = call(Http404())
    assert r.status_code == 404 and CONTRACT <= set(r.data)
    assert r.data["error_code"] == "RESOURCE_NOT_FOUND" and r.data["success"] is False


def test_validation_errors_are_field_level():
    r = call(serializers.ValidationError({"email": ["Enter a valid email address."]}))
    assert r.status_code == 400
    assert r.data["errors"]["email"]


def test_unauthenticated_requires_sign_in():
    class V(APIView):
        def get(self, request):
            return Response({})

    r = V.as_view()(factory.get("/x"))
    assert r.status_code in (401, 403) and r.data["error_code"] in (
        "AUTH_REQUIRED",
        "PERMISSION_DENIED",
    )


def test_unexpected_error_leaks_nothing():
    r = call(RuntimeError("SELECT * FROM users WHERE password='hunter2' /srv/app/secret.py"))
    assert r.status_code == 500
    assert r.data["error_code"] == "INTERNAL_ERROR" and r.data["retryable"] is True
    body = str(r.data)
    assert "hunter2" not in body and "SELECT" not in body and "/srv" not in body

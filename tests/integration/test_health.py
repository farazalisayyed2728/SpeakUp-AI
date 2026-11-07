import pytest
from django.core.cache import cache

pytestmark = pytest.mark.django_db


def test_live_ok(client):
    r = client.get("/health/live/")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_ready_ok(client):
    r = client.get("/health/ready/")
    assert r.status_code == 200
    assert r.json()["checks"] == {"database": True, "cache": True}


def test_ready_503_when_cache_down_and_leaks_nothing(client, monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("redis://user:secret@host:6379 refused")

    monkeypatch.setattr(cache, "set", boom)
    r = client.get("/health/ready/")
    assert r.status_code == 503
    assert r.json()["checks"]["cache"] is False
    assert "secret" not in r.content.decode()


def test_health_is_not_cacheable(client):
    assert "no-cache" in client.get("/health/live/")["Cache-Control"]

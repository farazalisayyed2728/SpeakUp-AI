import os
import threading
import time

import pytest
from django.test import override_settings

from apps.core import ratelimit
from apps.core.ratelimit import MemoryBackend, RedisBackend, Rule

RULE = Rule("t", limit=3, window=60)


def test_blocks_after_limit_and_reports_real_retry_after():
    results = [ratelimit.hit(RULE, "a") for _ in range(5)]
    assert [r.allowed for r in results] == [True, True, True, False, False]
    assert 1 <= results[-1].retry_after <= 60


def test_identifiers_and_scopes_are_isolated():
    for _ in range(4):
        ratelimit.hit(RULE, "alice")
    assert ratelimit.hit(RULE, "bob").allowed
    assert ratelimit.hit(Rule("other", 3, 60), "alice").allowed


def test_identifier_is_case_insensitive():
    for _ in range(3):
        ratelimit.hit(RULE, "Ada@Example.com")
    assert not ratelimit.hit(RULE, "ada@example.com").allowed


def test_window_expires():
    b = MemoryBackend()
    assert b.hit("k", 1)[0] == 1
    time.sleep(1.1)
    assert b.hit("k", 1)[0] == 1


def test_check_all_returns_none_when_ok_and_wait_when_blocked():
    assert ratelimit.check_all([(RULE, "x")]) is None
    for _ in range(3):
        ratelimit.hit(RULE, "x")
    assert ratelimit.check_all([(RULE, "x")]) >= 1


def _hammer(fn, n=60):
    out, lock = [], threading.Lock()

    def worker():
        d = fn()
        with lock:
            out.append(d.allowed)

    threads = [threading.Thread(target=worker) for _ in range(n)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return out


def test_memory_backend_is_exact_under_concurrency():
    rule = Rule("conc", limit=10, window=60)
    assert sum(_hammer(lambda: ratelimit.hit(rule, "u"))) == 10


def test_redis_outage_falls_back_instead_of_failing_open(monkeypatch):
    class Down:
        def hit(self, *a):
            raise ConnectionError("redis down")

    with override_settings(RATELIMIT_BACKEND="redis"):
        monkeypatch.setattr(ratelimit, "_primary", lambda: Down())
        results = [ratelimit.hit(RULE, "z").allowed for _ in range(5)]
    assert results == [True, True, True, False, False]


REDIS_URL = os.environ.get("REDIS_URL")


def _redis_up():
    try:
        import redis

        redis.Redis.from_url(REDIS_URL, socket_connect_timeout=1).ping()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not (REDIS_URL and _redis_up()), reason="needs a reachable REDIS_URL")
class TestRealRedis:
    def test_lua_limiter_is_exact_under_concurrency(self):
        backend = RedisBackend(REDIS_URL)
        rule = Rule(f"conc-{time.time_ns()}", limit=10, window=30)
        key = ratelimit._key(rule, "u")
        allowed = _hammer(lambda: ratelimit.Decision(backend.hit(key, 30)[0] <= 10, 0, 0), n=80)
        assert sum(allowed) == 10

    def test_key_always_gets_an_expiry(self):
        import redis

        backend = RedisBackend(REDIS_URL)
        key = f"rl:test:ttl-{time.time_ns()}"
        backend.hit(key, 30)
        ttl = redis.Redis.from_url(REDIS_URL).ttl(key)
        assert 0 < ttl <= 30

    def test_keys_do_not_contain_raw_identifiers(self):
        assert "ada@example.com" not in ratelimit._key(RULE, "ada@example.com")
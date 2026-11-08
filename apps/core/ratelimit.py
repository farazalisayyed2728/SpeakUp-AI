"""Atomic fixed-window rate limiting backed by Redis.

* Redis path: one Lua script does INCR + EXPIRE + TTL atomically, so concurrent requests can
  never over-admit or leave a counter without an expiry.
* Redis outage: we do NOT fail open. Auth abuse controls fall back to a per-process in-memory
  counter (weaker across multiple workers, but never "off") and log a warning.
* Counters are ephemeral. Redis is never the record of anything business-critical.
"""

import hashlib
import logging
import threading
import time
from dataclasses import dataclass

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Rule:
    scope: str
    limit: int
    window: int  # seconds


@dataclass(frozen=True)
class Decision:
    allowed: bool
    count: int
    retry_after: int  # seconds until the window resets (real value, never invented)


_LUA = """
local c = redis.call('INCR', KEYS[1])
if c == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
local ttl = redis.call('TTL', KEYS[1])
if ttl < 0 then redis.call('EXPIRE', KEYS[1], ARGV[1]); ttl = tonumber(ARGV[1]) end
return {c, ttl}
"""


class MemoryBackend:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, tuple[int, float]] = {}

    def hit(self, key: str, window: int) -> tuple[int, int]:
        now = time.monotonic()
        with self._lock:
            count, expires = self._data.get(key, (0, 0.0))
            if expires <= now:
                count, expires = 0, now + window
            count += 1
            self._data[key] = (count, expires)
            return count, max(1, int(expires - now + 0.999))

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class RedisBackend:
    def __init__(self, url: str) -> None:
        import redis

        self._client = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
        self._script = self._client.register_script(_LUA)

    def hit(self, key: str, window: int) -> tuple[int, int]:
        count, ttl = self._script(keys=[key], args=[window])
        return int(count), max(1, int(ttl))


_fallback = MemoryBackend()
_primary_cache: dict[tuple[str, str], object] = {}


def _primary():
    kind, url = settings.RATELIMIT_BACKEND, settings.REDIS_URL
    if kind == "memory":
        return _fallback
    if (kind, url) not in _primary_cache:
        _primary_cache[(kind, url)] = RedisBackend(url)
    return _primary_cache[(kind, url)]


def _key(rule: Rule, identifier: str) -> str:
    digest = hashlib.sha256(identifier.strip().lower().encode()).hexdigest()[:32]
    return f"rl:{rule.scope}:{digest}"  # hashed: no emails/IPs stored in Redis keys


def hit(rule: Rule, identifier: str) -> Decision:
    key = _key(rule, identifier)
    try:
        count, ttl = _primary().hit(key, rule.window)
    except Exception:
        logger.warning("rate limiter: Redis unavailable, using in-process fallback")
        count, ttl = _fallback.hit(key, rule.window)
    return Decision(allowed=count <= rule.limit, count=count, retry_after=ttl)


def check_all(checks: list[tuple[Rule, str]]) -> int | None:
    """Apply every (rule, identifier) pair. Returns seconds to wait if ANY is exceeded."""
    blocked = [d for d in (hit(rule, ident) for rule, ident in checks) if not d.allowed]
    return max(d.retry_after for d in blocked) if blocked else None


def reset_for_tests() -> None:
    _fallback.clear()

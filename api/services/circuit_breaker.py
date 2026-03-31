"""
Simple circuit breaker with Redis persistence.

States:
  CLOSED   → normal operation, requests pass through
  OPEN     → too many failures, requests fail-fast
  HALF_OPEN → after reset_timeout, allow one probe request

State persists across restarts via Redis keys.
"""
import time

import redis
from loguru import logger

from api.config import get_settings

settings = get_settings()


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5, reset_timeout: int = 30):
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._redis: redis.Redis | None = None
        self._key_failures = f"cb:{name}:failures"
        self._key_opened_at = f"cb:{name}:opened_at"

    def _get_redis(self) -> redis.Redis | None:
        if self._redis is None:
            try:
                self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
            except Exception:
                return None
        return self._redis

    def _get_state(self) -> str:
        r = self._get_redis()
        if not r:
            return "closed"  # Redis down → allow requests
        opened_at = r.get(self._key_opened_at)
        if opened_at:
            if time.time() - float(opened_at) >= self.reset_timeout:
                return "half_open"
            return "open"
        return "closed"

    @property
    def state(self) -> str:
        return self._get_state()

    def allow_request(self) -> bool:
        s = self._get_state()
        return s != "open"

    def record_success(self):
        r = self._get_redis()
        if not r:
            return
        if self._get_state() == "half_open":
            logger.info(f"Circuit breaker [{self.name}]: HALF_OPEN → CLOSED (probe succeeded)")
        r.delete(self._key_failures, self._key_opened_at)

    def record_failure(self):
        r = self._get_redis()
        if not r:
            return
        count = r.incr(self._key_failures)
        r.expire(self._key_failures, self.reset_timeout * 3)
        if count >= self.failure_threshold:
            if not r.exists(self._key_opened_at):
                logger.warning(
                    f"Circuit breaker [{self.name}]: OPEN after {count} failures "
                    f"(will retry in {self.reset_timeout}s)"
                )
            r.setex(self._key_opened_at, self.reset_timeout, str(time.time()))


# Shared breakers for external services
auth0_breaker = CircuitBreaker("auth0", failure_threshold=5, reset_timeout=30)


# Per-workspace circuit breakers (lazy creation)
_workspace_breakers: dict[str, CircuitBreaker] = {}

def get_workspace_breaker(workspace_id: str) -> CircuitBreaker:
    """Get or create a per-workspace circuit breaker."""
    if workspace_id not in _workspace_breakers:
        _workspace_breakers[workspace_id] = CircuitBreaker(
            f"ws:{workspace_id[:8]}", failure_threshold=5, reset_timeout=30
        )
    return _workspace_breakers[workspace_id]

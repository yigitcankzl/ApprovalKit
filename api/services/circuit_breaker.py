"""
Simple circuit breaker — no external dependencies.

States:
  CLOSED   → normal operation, requests pass through
  OPEN     → too many failures, requests fail-fast
  HALF_OPEN → after reset_timeout, allow one probe request

Usage:
    breaker = CircuitBreaker("auth0", failure_threshold=5, reset_timeout=30)

    if not breaker.allow_request():
        raise RuntimeError("Auth0 circuit is OPEN — failing fast")

    try:
        result = await call_auth0(...)
        breaker.record_success()
    except Exception:
        breaker.record_failure()
        raise
"""
import time
from enum import Enum
from loguru import logger


class _State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5, reset_timeout: int = 30):
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._state = _State.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0

    @property
    def state(self) -> str:
        return self._current_state().value

    def _current_state(self) -> _State:
        if self._state == _State.OPEN:
            if time.monotonic() - self._last_failure_time >= self.reset_timeout:
                return _State.HALF_OPEN
        return self._state

    def allow_request(self) -> bool:
        s = self._current_state()
        if s == _State.CLOSED:
            return True
        if s == _State.HALF_OPEN:
            return True  # allow one probe
        return False  # OPEN

    def record_success(self):
        if self._current_state() == _State.HALF_OPEN:
            logger.info(f"Circuit breaker [{self.name}]: HALF_OPEN → CLOSED (probe succeeded)")
        self._state = _State.CLOSED
        self._failure_count = 0

    def record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            if self._state != _State.OPEN:
                logger.warning(
                    f"Circuit breaker [{self.name}]: OPEN after {self._failure_count} failures "
                    f"(will retry in {self.reset_timeout}s)"
                )
            self._state = _State.OPEN


# Shared breakers for external services
auth0_breaker = CircuitBreaker("auth0", failure_threshold=5, reset_timeout=30)

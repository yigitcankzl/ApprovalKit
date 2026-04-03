"""Tests for circuit breaker (api/services/circuit_breaker.py)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
import pytest
from unittest.mock import MagicMock, patch


class TestCircuitBreakerLogic:
    """Test circuit breaker state transitions without real Redis."""

    def _make_breaker(self):
        from api.services.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker("test", failure_threshold=3, reset_timeout=10)
        # Mock Redis
        mock_redis = MagicMock()
        cb._redis = mock_redis
        cb._get_redis = MagicMock(return_value=mock_redis)
        return cb, mock_redis

    def test_initial_state_closed(self):
        cb, redis = self._make_breaker()
        redis.get.return_value = None  # no opened_at key
        assert cb.state == "closed"

    def test_allow_request_when_closed(self):
        cb, redis = self._make_breaker()
        redis.get.return_value = None
        assert cb.allow_request() is True

    def test_open_state_blocks_requests(self):
        cb, redis = self._make_breaker()
        # opened_at set recently
        redis.get.return_value = str(time.time())
        assert cb.state == "open"
        assert cb.allow_request() is False

    def test_half_open_after_timeout(self):
        cb, redis = self._make_breaker()
        # opened_at set long ago (> reset_timeout)
        redis.get.return_value = str(time.time() - 20)
        assert cb.state == "half_open"
        assert cb.allow_request() is True

    def test_record_success_clears_state(self):
        cb, redis = self._make_breaker()
        redis.get.return_value = str(time.time() - 20)  # half_open
        cb.record_success()
        redis.delete.assert_called_once()

    def test_record_failure_increments(self):
        cb, redis = self._make_breaker()
        redis.incr.return_value = 1
        cb.record_failure()
        redis.incr.assert_called_once()

    def test_record_failure_opens_circuit_at_threshold(self):
        cb, redis = self._make_breaker()
        redis.incr.return_value = 3  # equals threshold
        redis.exists.return_value = False
        cb.record_failure()
        redis.setex.assert_called_once()

    def test_record_failure_below_threshold_no_open(self):
        cb, redis = self._make_breaker()
        redis.incr.return_value = 1  # below threshold
        cb.record_failure()
        redis.setex.assert_not_called()

    def test_redis_unavailable_returns_closed(self):
        from api.services.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker("test-no-redis", failure_threshold=3, reset_timeout=10)
        cb._get_redis = MagicMock(return_value=None)
        assert cb.state == "closed"
        assert cb.allow_request() is True

    def test_redis_unavailable_record_success_noop(self):
        from api.services.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker("test-no-redis", failure_threshold=3, reset_timeout=10)
        cb._get_redis = MagicMock(return_value=None)
        cb.record_success()  # should not raise

    def test_redis_unavailable_record_failure_noop(self):
        from api.services.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker("test-no-redis", failure_threshold=3, reset_timeout=10)
        cb._get_redis = MagicMock(return_value=None)
        cb.record_failure()  # should not raise


class TestCircuitBreakerInstances:
    def test_auth0_breaker_exists(self):
        from api.services.circuit_breaker import auth0_breaker
        assert auth0_breaker.name == "auth0"
        assert auth0_breaker.failure_threshold == 5

    def test_workspace_breaker_created(self):
        from api.services.circuit_breaker import get_workspace_breaker
        breaker = get_workspace_breaker("ws-test-123")
        assert breaker.name.startswith("ws:")
        assert breaker.failure_threshold == 5

    def test_workspace_breaker_cached(self):
        from api.services.circuit_breaker import get_workspace_breaker
        b1 = get_workspace_breaker("ws-cache-test")
        b2 = get_workspace_breaker("ws-cache-test")
        assert b1 is b2

    def test_different_workspace_different_breaker(self):
        from api.services.circuit_breaker import get_workspace_breaker
        b1 = get_workspace_breaker("ws-aaa")
        b2 = get_workspace_breaker("ws-bbb")
        assert b1 is not b2

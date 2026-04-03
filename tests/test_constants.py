"""Tests for constants (api/constants.py)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.constants import *


class TestRedisKeyPatterns:
    def test_rate_limit_pattern(self):
        assert "{key}" in REDIS_KEY_RATE_LIMIT

    def test_cooldown_pattern(self):
        assert "{rule_id}" in REDIS_KEY_COOLDOWN

    def test_idempotency_pattern(self):
        assert "{key}" in REDIS_KEY_IDEMPOTENCY

    def test_budget_daily_pattern(self):
        assert "{agent_id}" in REDIS_KEY_BUDGET_DAILY

    def test_budget_weekly_pattern(self):
        assert "{agent_id}" in REDIS_KEY_BUDGET_WEEKLY

    def test_budget_monthly_pattern(self):
        assert "{agent_id}" in REDIS_KEY_BUDGET_MONTHLY

    def test_agent_rate_pattern(self):
        assert "{agent_id}" in REDIS_KEY_AGENT_RATE
        assert "{connection}" in REDIS_KEY_AGENT_RATE

    def test_sse_channel_is_string(self):
        assert isinstance(REDIS_KEY_SSE_CHANNEL, str)

    def test_key_format_works(self):
        key = REDIS_KEY_BUDGET_DAILY.format(agent_id="agent-123")
        assert "agent-123" in key
        assert "{agent_id}" not in key


class TestForbiddenKeys:
    def test_proto_forbidden(self):
        assert "__proto__" in FORBIDDEN_PARAM_KEYS

    def test_constructor_forbidden(self):
        assert "constructor" in FORBIDDEN_PARAM_KEYS

    def test_where_forbidden(self):
        assert "$where" in FORBIDDEN_PARAM_KEYS

    def test_is_set(self):
        assert isinstance(FORBIDDEN_PARAM_KEYS, set)


class TestLimits:
    def test_max_body_size_is_1mb(self):
        assert MAX_BODY_SIZE_BYTES == 1 * 1024 * 1024

    def test_cooldown_window_seconds(self):
        assert COOLDOWN_WINDOW_SECONDS == 3600

    def test_idempotency_ttl(self):
        assert IDEMPOTENCY_TTL_SECONDS == 86400

    def test_scope_creep_lookback_positive(self):
        assert SCOPE_CREEP_LOOKBACK > 0

    def test_anomaly_threshold_multiplier(self):
        assert ANOMALY_THRESHOLD_MULTIPLIER == 3

    def test_decision_rate_limit(self):
        assert DECISION_RATE_LIMIT_PER_JOB > 0
        assert DECISION_RATE_WINDOW_SECONDS > 0


class TestBudgetConstants:
    def test_budget_daily_ttl(self):
        assert BUDGET_DAILY_TTL == 86400

    def test_budget_weekly_ttl(self):
        assert BUDGET_WEEKLY_TTL == 604800

    def test_budget_monthly_ttl(self):
        assert BUDGET_MONTHLY_TTL == 2678400

    def test_daily_less_than_weekly_ttl(self):
        assert BUDGET_DAILY_TTL < BUDGET_WEEKLY_TTL

    def test_weekly_less_than_monthly_ttl(self):
        assert BUDGET_WEEKLY_TTL < BUDGET_MONTHLY_TTL


class TestAgentRateConstants:
    def test_agent_rate_window(self):
        assert AGENT_RATE_WINDOW_SECONDS == 3600

    def test_default_approval_expiry(self):
        assert DEFAULT_APPROVAL_EXPIRY_SECONDS == 1800


class TestWebhookConstants:
    def test_webhook_timeout(self):
        assert WEBHOOK_TIMEOUT_SECONDS == 10

    def test_webhook_max_retries(self):
        assert WEBHOOK_MAX_RETRIES == 3

    def test_retries_positive(self):
        assert WEBHOOK_MAX_RETRIES > 0


class TestNotificationChannels:
    def test_default_channels(self):
        assert isinstance(DEFAULT_NOTIFY_CHANNELS, list)
        assert len(DEFAULT_NOTIFY_CHANNELS) > 0

    def test_urgent_channels(self):
        assert isinstance(DEFAULT_URGENT_CHANNELS, list)
        assert len(DEFAULT_URGENT_CHANNELS) > 0

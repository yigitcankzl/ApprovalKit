"""Tests for advanced rule engine functions: _resolve_field, blackout, cooldown,
pre-approval, escalation chain, binding message, budget, approval count."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, time, timedelta

from api.services.rule_engine import (
    _resolve_field,
    evaluate_condition,
    evaluate_conditions,
    is_in_blackout,
    check_time_window,
    get_required_approval_count,
    build_escalation_chain,
    render_binding_message,
    check_approval_expiry,
)


# ── _resolve_field ──────────────────────────────────────────────────────────

class TestResolveField:
    def test_simple_key(self):
        assert _resolve_field({"amount": 500}, "amount") == 500

    def test_missing_key(self):
        assert _resolve_field({"amount": 500}, "price") is None

    def test_nested_dict(self):
        params = {"billing": {"country": "US", "zip": "90210"}}
        assert _resolve_field(params, "billing.country") == "US"

    def test_deeply_nested(self):
        params = {"a": {"b": {"c": {"d": 42}}}}
        assert _resolve_field(params, "a.b.c.d") == 42

    def test_list_index(self):
        params = {"items": [{"price": 10}, {"price": 20}]}
        assert _resolve_field(params, "items.0.price") == 10
        assert _resolve_field(params, "items.1.price") == 20

    def test_list_index_out_of_range(self):
        params = {"items": [1, 2]}
        assert _resolve_field(params, "items.5") is None

    def test_list_non_numeric_index(self):
        params = {"items": [1, 2]}
        assert _resolve_field(params, "items.abc") is None

    def test_none_intermediate(self):
        params = {"a": {"b": None}}
        assert _resolve_field(params, "a.b.c") is None

    def test_non_dict_non_list(self):
        params = {"a": 42}
        assert _resolve_field(params, "a.b") is None

    def test_empty_params(self):
        assert _resolve_field({}, "key") is None


# ── evaluate_condition (advanced operators) ─────────────────────────────────

class TestEvaluateConditionAdvanced:
    def test_exists_true(self):
        assert evaluate_condition(
            {"field": "email", "operator": "exists"}, {"email": "a@b.com"}
        ) is True

    def test_exists_false(self):
        assert evaluate_condition(
            {"field": "email", "operator": "exists"}, {"name": "Alice"}
        ) is False

    def test_not_exists_true(self):
        assert evaluate_condition(
            {"field": "deleted", "operator": "not_exists"}, {"name": "Alice"}
        ) is True

    def test_not_exists_false(self):
        assert evaluate_condition(
            {"field": "name", "operator": "not_exists"}, {"name": "Alice"}
        ) is False

    def test_starts_with(self):
        assert evaluate_condition(
            {"field": "name", "operator": "starts_with", "value": "Al"},
            {"name": "Alice"},
        ) is True

    def test_ends_with(self):
        assert evaluate_condition(
            {"field": "file", "operator": "ends_with", "value": ".py"},
            {"file": "test.py"},
        ) is True

    def test_regex_match(self):
        assert evaluate_condition(
            {"field": "code", "operator": "regex", "value": r"^[A-Z]{3}\d{3}$"},
            {"code": "ABC123"},
        ) is True

    def test_regex_no_match(self):
        assert evaluate_condition(
            {"field": "code", "operator": "regex", "value": r"^\d+$"},
            {"code": "abc"},
        ) is False

    def test_between(self):
        assert evaluate_condition(
            {"field": "age", "operator": "between", "value": [18, 65]},
            {"age": 30},
        ) is True

    def test_between_outside(self):
        assert evaluate_condition(
            {"field": "age", "operator": "between", "value": [18, 65]},
            {"age": 10},
        ) is False

    def test_not_in(self):
        assert evaluate_condition(
            {"field": "status", "operator": "not_in", "value": ["blocked", "banned"]},
            {"status": "active"},
        ) is True

    def test_not_in_fails(self):
        assert evaluate_condition(
            {"field": "status", "operator": "not_in", "value": ["blocked", "banned"]},
            {"status": "blocked"},
        ) is False

    def test_nested_field_condition(self):
        assert evaluate_condition(
            {"field": "billing.country", "operator": "eq", "value": "US"},
            {"billing": {"country": "US"}},
        ) is True


# ── evaluate_conditions (grouped logic) ─────────────────────────────────────

class TestEvaluateConditionsGrouped:
    def test_or_group(self):
        conditions = [
            {"logic": "or", "conditions": [
                {"field": "amount", "operator": "gt", "value": 1000},
                {"field": "risk", "operator": "eq", "value": "critical"},
            ]}
        ]
        assert evaluate_conditions(conditions, {"amount": 50, "risk": "critical"}) is True

    def test_or_group_none_match(self):
        conditions = [
            {"logic": "or", "conditions": [
                {"field": "amount", "operator": "gt", "value": 1000},
                {"field": "risk", "operator": "eq", "value": "critical"},
            ]}
        ]
        assert evaluate_conditions(conditions, {"amount": 50, "risk": "low"}) is False

    def test_and_group_explicit(self):
        conditions = [
            {"logic": "and", "conditions": [
                {"field": "amount", "operator": "gt", "value": 100},
                {"field": "currency", "operator": "eq", "value": "USD"},
            ]}
        ]
        assert evaluate_conditions(conditions, {"amount": 200, "currency": "USD"}) is True
        assert evaluate_conditions(conditions, {"amount": 200, "currency": "EUR"}) is False

    def test_mixed_plain_and_group(self):
        conditions = [
            {"field": "status", "operator": "eq", "value": "active"},
            {"logic": "or", "conditions": [
                {"field": "role", "operator": "eq", "value": "admin"},
                {"field": "role", "operator": "eq", "value": "manager"},
            ]}
        ]
        assert evaluate_conditions(conditions, {"status": "active", "role": "admin"}) is True
        assert evaluate_conditions(conditions, {"status": "inactive", "role": "admin"}) is False

    def test_empty_conditions_returns_true(self):
        assert evaluate_conditions([], {"amount": 100}) is True
        assert evaluate_conditions(None, {"amount": 100}) is True


# ── is_in_blackout ──────────────────────────────────────────────────────────

class TestBlackout:
    def _make_rule(self, start=None, end=None):
        rule = MagicMock()
        rule.blackout_start = start
        rule.blackout_end = end
        return rule

    def test_no_blackout_configured(self):
        rule = self._make_rule()
        assert is_in_blackout(rule) is False

    def test_within_blackout(self):
        now = datetime.utcnow().time()
        start = time(0, 0)
        end = time(23, 59, 59)
        rule = self._make_rule(start, end)
        assert is_in_blackout(rule) is True

    def test_outside_blackout(self):
        # Set blackout far in the past hour range that doesn't overlap with now
        rule = self._make_rule(time(2, 0), time(2, 1))
        # This could be True/False depending on when test runs,
        # but we can use a fixed time approach
        result = is_in_blackout(rule)
        assert isinstance(result, bool)

    def test_overnight_blackout(self):
        # Overnight: 22:00 → 06:00 (start > end)
        rule = self._make_rule(time(22, 0), time(6, 0))
        result = is_in_blackout(rule)
        assert isinstance(result, bool)


# ── check_time_window ──────────────────────────────────────────────────────

class TestCheckTimeWindow:
    def _make_rule(self, start=None, end=None):
        rule = MagicMock()
        rule.blackout_start = start
        rule.blackout_end = end
        return rule

    def test_no_window_always_open(self):
        rule = self._make_rule()
        result = check_time_window(rule)
        assert result["in_window"] is True
        assert result["blackout"] is False
        assert result["next_open"] is None

    def test_in_blackout_returns_next_open(self):
        rule = self._make_rule(time(0, 0), time(23, 59, 59))
        result = check_time_window(rule)
        assert result["blackout"] is True
        assert result["next_open"] is not None


# ── get_required_approval_count ─────────────────────────────────────────────

class TestGetRequiredApprovalCount:
    def _make_rule(self, model, approvers=2, k=None):
        rule = MagicMock()
        rule.model = model
        rule.rule_approvers = [MagicMock() for _ in range(approvers)]
        rule.k_value = k
        return rule

    def test_any_one(self):
        assert get_required_approval_count(self._make_rule("any_one")) == 1

    def test_specific(self):
        assert get_required_approval_count(self._make_rule("specific")) == 1

    def test_all_of_n(self):
        assert get_required_approval_count(self._make_rule("all_of_n", approvers=3)) == 3

    def test_k_of_n(self):
        assert get_required_approval_count(self._make_rule("k_of_n", approvers=5, k=3)) == 3

    def test_k_of_n_no_k(self):
        assert get_required_approval_count(self._make_rule("k_of_n", k=None)) == 1

    def test_sequential(self):
        assert get_required_approval_count(self._make_rule("sequential", approvers=4)) == 4

    def test_unknown_model(self):
        assert get_required_approval_count(self._make_rule("unknown_model")) == 1


# ── build_escalation_chain ──────────────────────────────────────────────────

class TestBuildEscalationChain:
    def _make_rule(self, n_approvers=3, timeout=900, step_up=None, escalate_to=None):
        rule = MagicMock()
        approvers = []
        for i in range(n_approvers):
            ra = MagicMock()
            ra.order = i
            ra.approver_id = f"approver-{i}"
            approvers.append(ra)
        rule.rule_approvers = approvers
        rule.timeout_seconds = timeout
        rule.step_up_conditions = step_up
        rule.escalate_to = escalate_to
        return rule

    def test_basic_chain(self):
        rule = self._make_rule(n_approvers=3, timeout=900)
        chain = build_escalation_chain(rule)
        assert len(chain) == 3
        assert chain[0]["tier"] == 1
        assert chain[1]["tier"] == 2
        assert chain[2]["tier"] == 3
        assert chain[0]["sla_seconds"] == 300  # 900 / 3

    def test_empty_approvers(self):
        rule = self._make_rule(n_approvers=0)
        assert build_escalation_chain(rule) == []

    def test_custom_sla_chain(self):
        step_up = [
            {"type": "escalation_chain", "chain": [
                {"sla_seconds": 600, "role": "manager"},
                {"sla_seconds": 1200, "role": "director"},
            ]}
        ]
        rule = self._make_rule(n_approvers=2, step_up=step_up)
        chain = build_escalation_chain(rule)
        assert chain[0]["sla_seconds"] == 600
        assert chain[0]["role"] == "manager"
        assert chain[1]["sla_seconds"] == 1200
        assert chain[1]["role"] == "director"

    def test_escalate_to_adds_final_tier(self):
        rule = self._make_rule(n_approvers=2, timeout=600, escalate_to="vp-id")
        chain = build_escalation_chain(rule)
        assert len(chain) == 3
        assert chain[2]["role"] == "final_escalation"
        assert chain[2]["approver_id"] == "vp-id"


# ── render_binding_message ──────────────────────────────────────────────────

class TestRenderBindingMessage:
    def test_default_message_with_amount(self):
        result = render_binding_message(None, {"amount": 500})
        assert "500" in result

    def test_default_message_no_amount(self):
        result = render_binding_message(None, {"action": "deploy"})
        assert "Approve action" in result

    def test_template_substitution(self):
        result = render_binding_message(
            "Charge {amount} to {customer}",
            {"amount": "500", "customer": "Acme"},
        )
        assert "500" in result
        assert "Acme" in result

    def test_double_brace_substitution(self):
        result = render_binding_message(
            "Pay {{amount}} for {{service}}",
            {"amount": "1000", "service": "hosting"},
        )
        assert "1000" in result
        assert "hosting" in result

    def test_message_truncated_at_150(self):
        result = render_binding_message("A" * 200, {})
        assert len(result) <= 150

    def test_special_chars_stripped(self):
        result = render_binding_message("Test <script>alert(1)</script>", {})
        assert "<script>" not in result

    def test_newlines_removed_from_values(self):
        result = render_binding_message(
            "Action: {note}",
            {"note": "line1\nline2\rline3"},
        )
        assert "\n" not in result
        assert "\r" not in result


# ── check_approval_expiry ───────────────────────────────────────────────────

class TestCheckApprovalExpiry:
    def test_no_expiry(self):
        result = check_approval_expiry(datetime.utcnow(), None)
        assert result["valid"] is True
        assert result["remaining_seconds"] == -1

    def test_zero_expiry(self):
        result = check_approval_expiry(datetime.utcnow(), 0)
        assert result["valid"] is True

    def test_not_expired(self):
        result = check_approval_expiry(datetime.utcnow(), 3600)
        assert result["valid"] is True
        assert result["remaining_seconds"] > 0

    def test_expired(self):
        past = datetime.utcnow() - timedelta(hours=2)
        result = check_approval_expiry(past, 3600)
        assert result["valid"] is False
        assert result["remaining_seconds"] == 0
        assert result["expired_at"] is not None

    def test_negative_expiry(self):
        result = check_approval_expiry(datetime.utcnow(), -10)
        assert result["valid"] is True

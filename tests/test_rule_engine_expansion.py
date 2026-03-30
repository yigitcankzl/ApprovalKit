"""Tests for Rule Engine expansion features.

1. Schema operator fix — all 15 operators accepted
2. Agent rate limiting — check_agent_rate_limit
3. Approval expiry — check_approval_expiry
4. Rule chaining — trigger_rules field
5. Rule templates — RULE_TEMPLATES data
"""
import asyncio
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# ─────────────────────── helpers ───────────────────────

def run(coro):
    return asyncio.run(coro)


# ═══════════════════════ Feature 1: Schema Operator Fix ═══════════════════════

class TestSchemaOperatorFix(unittest.TestCase):
    """All 15 operators should be accepted by ConditionSchema."""

    def test_all_operators_accepted(self):
        from api.schemas.rule import ConditionSchema
        operators = [
            "eq", "ne", "gt", "gte", "lt", "lte",
            "in", "not_in", "contains",
            "starts_with", "ends_with", "regex", "between",
            "exists", "not_exists",
        ]
        for op in operators:
            cs = ConditionSchema(field="amount", operator=op, value=100)
            self.assertEqual(cs.operator, op, f"Operator '{op}' should be accepted")

    def test_invalid_operator_rejected(self):
        from api.schemas.rule import ConditionSchema
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            ConditionSchema(field="amount", operator="invalid_op", value=100)


# ═══════════════════════ Feature 2: Agent Rate Limiting ═══════════════════════

class TestAgentRateLimit(unittest.TestCase):

    def test_rate_limit_allowed_when_under_limit(self):
        from api.services.rule_engine import check_agent_rate_limit
        redis = AsyncMock()
        redis.get = AsyncMock(return_value="5")
        result = run(check_agent_rate_limit("agent-1", "stripe-prod", 10, redis))
        self.assertTrue(result["allowed"])
        self.assertEqual(result["current"], 5)
        self.assertEqual(result["limit"], 10)

    def test_rate_limit_blocked_when_at_limit(self):
        from api.services.rule_engine import check_agent_rate_limit
        redis = AsyncMock()
        redis.get = AsyncMock(return_value="10")
        result = run(check_agent_rate_limit("agent-1", "stripe-prod", 10, redis))
        self.assertFalse(result["allowed"])
        self.assertEqual(result["current"], 10)

    def test_rate_limit_unlimited_when_zero(self):
        from api.services.rule_engine import check_agent_rate_limit
        redis = AsyncMock()
        result = run(check_agent_rate_limit("agent-1", "stripe-prod", 0, redis))
        self.assertTrue(result["allowed"])

    def test_rate_limit_unlimited_when_none(self):
        from api.services.rule_engine import check_agent_rate_limit
        redis = AsyncMock()
        result = run(check_agent_rate_limit("agent-1", "stripe-prod", None, redis))
        self.assertTrue(result["allowed"])

    def test_increment_agent_rate(self):
        from api.services.rule_engine import increment_agent_rate
        redis = AsyncMock()
        pipe = AsyncMock()
        redis.pipeline = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=[6, True])
        run(increment_agent_rate("agent-1", "stripe-prod", redis))
        pipe.incr.assert_called_once()
        pipe.expire.assert_called_once()


# ═══════════════════════ Feature 3: Approval Expiry ═══════════════════════

class TestApprovalExpiry(unittest.TestCase):

    def test_approval_still_valid(self):
        from api.services.rule_engine import check_approval_expiry
        approved_at = datetime.utcnow() - timedelta(minutes=5)
        result = check_approval_expiry(approved_at, 1800)  # 30 min expiry
        self.assertTrue(result["valid"])
        self.assertGreater(result["remaining_seconds"], 0)

    def test_approval_expired(self):
        from api.services.rule_engine import check_approval_expiry
        approved_at = datetime.utcnow() - timedelta(hours=1)
        result = check_approval_expiry(approved_at, 1800)  # 30 min expiry
        self.assertFalse(result["valid"])
        self.assertEqual(result["remaining_seconds"], 0)

    def test_no_expiry_always_valid(self):
        from api.services.rule_engine import check_approval_expiry
        approved_at = datetime.utcnow() - timedelta(days=30)
        result = check_approval_expiry(approved_at, None)
        self.assertTrue(result["valid"])
        self.assertEqual(result["remaining_seconds"], -1)

    def test_zero_expiry_always_valid(self):
        from api.services.rule_engine import check_approval_expiry
        approved_at = datetime.utcnow() - timedelta(days=30)
        result = check_approval_expiry(approved_at, 0)
        self.assertTrue(result["valid"])


# ═══════════════════════ Feature 4: Rule Chaining ═══════════════════════

class TestRuleChaining(unittest.TestCase):

    def test_trigger_rules_field_in_schema(self):
        from api.schemas.rule import RuleCreate
        from api.models.rule import ApprovalModel
        import uuid
        rule_data = RuleCreate(
            name="Test chaining",
            connection="stripe-prod",
            action="charge",
            model=ApprovalModel.ANY_ONE,
            approver_ids=[uuid.uuid4()],
            trigger_rules=[
                {"connection": "gmail-prod", "action": "send_email", "params": {"subject": "Invoice"}}
            ],
        )
        self.assertIsNotNone(rule_data.trigger_rules)
        self.assertEqual(len(rule_data.trigger_rules), 1)
        self.assertEqual(rule_data.trigger_rules[0]["connection"], "gmail-prod")

    def test_on_approve_actions_field_in_schema(self):
        from api.schemas.rule import RuleCreate
        from api.models.rule import ApprovalModel
        import uuid
        rule_data = RuleCreate(
            name="Test on_approve",
            connection="stripe-prod",
            action="charge",
            model=ApprovalModel.ANY_ONE,
            approver_ids=[uuid.uuid4()],
            on_approve_actions=[
                {"connection": "slack-prod", "action": "send_message", "params": {"text": "Payment done"}}
            ],
        )
        self.assertIsNotNone(rule_data.on_approve_actions)


# ═══════════════════════ Feature 5: Rule Templates ═══════════════════════

class TestRuleTemplates(unittest.TestCase):

    def test_templates_exist(self):
        from api.services.rule_engine import RULE_TEMPLATES
        self.assertGreaterEqual(len(RULE_TEMPLATES), 5)

    def test_template_structure(self):
        from api.services.rule_engine import RULE_TEMPLATES
        required_keys = {"id", "name", "description", "category", "connection", "action", "model"}
        for tpl in RULE_TEMPLATES:
            for key in required_keys:
                self.assertIn(key, tpl, f"Template '{tpl.get('id', '?')}' missing key '{key}'")

    def test_template_categories(self):
        from api.services.rule_engine import RULE_TEMPLATES
        categories = {t["category"] for t in RULE_TEMPLATES}
        self.assertIn("finance", categories)
        self.assertIn("devops", categories)
        self.assertIn("communication", categories)
        self.assertIn("compliance", categories)

    def test_template_ids_unique(self):
        from api.services.rule_engine import RULE_TEMPLATES
        ids = [t["id"] for t in RULE_TEMPLATES]
        self.assertEqual(len(ids), len(set(ids)), "Template IDs must be unique")

    def test_high_value_payment_template(self):
        from api.services.rule_engine import RULE_TEMPLATES
        tpl = next(t for t in RULE_TEMPLATES if t["id"] == "high_value_payment")
        self.assertEqual(tpl["connection"], "stripe-prod")
        self.assertEqual(tpl["action"], "charge")
        self.assertEqual(tpl["model"], "sequential")
        self.assertIn("max_requests_per_hour", tpl)
        self.assertIn("approval_expiry_seconds", tpl)
        self.assertIn("approval_checklist", tpl)

    def test_production_deploy_template_has_blackout(self):
        from api.services.rule_engine import RULE_TEMPLATES
        tpl = next(t for t in RULE_TEMPLATES if t["id"] == "production_deploy")
        self.assertEqual(tpl["blackout_start"], "22:00")
        self.assertEqual(tpl["blackout_end"], "06:00")

    def test_bulk_email_template_has_trigger_rules(self):
        from api.services.rule_engine import RULE_TEMPLATES
        tpl = next(t for t in RULE_TEMPLATES if t["id"] == "bulk_email")
        self.assertIn("trigger_rules", tpl)
        self.assertGreater(len(tpl["trigger_rules"]), 0)


# ═══════════════════════ Existing Engine — Regression ═══════════════════════

class TestExistingEngineRegression(unittest.TestCase):

    def test_evaluate_condition_all_operators(self):
        from api.services.rule_engine import evaluate_condition
        # gt
        self.assertTrue(evaluate_condition({"field": "amount", "operator": "gt", "value": 100}, {"amount": 200}))
        # starts_with
        self.assertTrue(evaluate_condition({"field": "name", "operator": "starts_with", "value": "John"}, {"name": "John Doe"}))
        # ends_with
        self.assertTrue(evaluate_condition({"field": "email", "operator": "ends_with", "value": "@test.com"}, {"email": "user@test.com"}))
        # regex
        self.assertTrue(evaluate_condition({"field": "code", "operator": "regex", "value": r"^[A-Z]{3}\d{3}$"}, {"code": "ABC123"}))
        # between
        self.assertTrue(evaluate_condition({"field": "price", "operator": "between", "value": [10, 50]}, {"price": 30}))
        # exists
        self.assertTrue(evaluate_condition({"field": "amount", "operator": "exists", "value": None}, {"amount": 100}))
        # not_exists
        self.assertTrue(evaluate_condition({"field": "missing", "operator": "not_exists", "value": None}, {"amount": 100}))


# ═══════════════════════ Schema New Fields ═══════════════════════

class TestSchemaNewFields(unittest.TestCase):

    def test_create_schema_with_rate_limit(self):
        from api.schemas.rule import RuleCreate
        from api.models.rule import ApprovalModel
        import uuid
        rule = RuleCreate(
            name="Rate limited",
            connection="stripe",
            action="charge",
            model=ApprovalModel.ANY_ONE,
            approver_ids=[uuid.uuid4()],
            max_requests_per_hour=100,
        )
        self.assertEqual(rule.max_requests_per_hour, 100)

    def test_create_schema_with_approval_expiry(self):
        from api.schemas.rule import RuleCreate
        from api.models.rule import ApprovalModel
        import uuid
        rule = RuleCreate(
            name="Expiring",
            connection="github",
            action="deploy",
            model=ApprovalModel.SPECIFIC,
            approver_ids=[uuid.uuid4()],
            approval_expiry_seconds=600,
        )
        self.assertEqual(rule.approval_expiry_seconds, 600)

    def test_response_schema_has_new_fields(self):
        from api.schemas.rule import RuleResponse
        fields = RuleResponse.model_fields
        self.assertIn("max_requests_per_hour", fields)
        self.assertIn("approval_expiry_seconds", fields)
        self.assertIn("trigger_rules", fields)
        self.assertIn("on_approve_actions", fields)


if __name__ == "__main__":
    unittest.main()

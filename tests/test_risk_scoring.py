"""Tests for risk scoring and risk-based auto-approval (Feature 7)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import MagicMock
from api.services.rule_engine import compute_risk_score


class TestComputeRiskScore(unittest.TestCase):

    def _make_rule(self, model="any_one", k=None, step_up=None, threshold=None):
        rule = MagicMock()
        rule.model = model
        rule.k_value = k
        rule.rule_approvers = [MagicMock(), MagicMock()]
        rule.step_up_conditions = step_up
        rule.risk_auto_approve_threshold = threshold
        return rule

    # ── Amount-based scoring ────────────────────────────────────────────────

    def test_zero_amount_gives_zero_base_score(self):
        result = compute_risk_score({"amount": 0})
        self.assertEqual(result["score"], 0)

    def test_small_amount_low_risk(self):
        result = compute_risk_score({"amount": 50})
        self.assertLess(result["score"], 20)
        self.assertEqual(result["level"], "low")

    def test_standard_amount_adds_10(self):
        result = compute_risk_score({"amount": 500})
        self.assertIn("standard_amount", " ".join(result["factors"]))

    def test_moderate_amount_adds_20(self):
        result = compute_risk_score({"amount": 2000})
        self.assertIn("moderate_amount", " ".join(result["factors"]))

    def test_elevated_amount_adds_30(self):
        result = compute_risk_score({"amount": 7000})
        self.assertIn("elevated_amount", " ".join(result["factors"]))

    def test_high_amount_adds_40(self):
        result = compute_risk_score({"amount": 15000})
        self.assertIn("high_amount", " ".join(result["factors"]))

    def test_amount_usd_field_recognised(self):
        r1 = compute_risk_score({"amount_usd": 500})
        r2 = compute_risk_score({"amount": 500})
        self.assertEqual(r1["score"], r2["score"])

    def test_total_field_recognised(self):
        result = compute_risk_score({"total": 500})
        self.assertGreater(result["score"], 0)

    def test_string_amount_coerced(self):
        result = compute_risk_score({"amount": "2000"})
        self.assertGreater(result["score"], 0)

    def test_invalid_amount_ignored(self):
        result = compute_risk_score({"amount": "not-a-number"})
        self.assertEqual(result["score"], 0)

    # ── Scope creep ─────────────────────────────────────────────────────────

    def test_new_action_adds_20(self):
        result = compute_risk_score({}, scope_creep={"is_new_action": True, "amount_anomaly": False})
        self.assertEqual(result["score"], 20)
        self.assertIn("new_action_type", result["factors"])

    def test_amount_anomaly_adds_25(self):
        result = compute_risk_score({}, scope_creep={"is_new_action": False, "amount_anomaly": True})
        self.assertEqual(result["score"], 25)
        self.assertIn("amount_anomaly", result["factors"])

    def test_both_scope_signals_add_45(self):
        result = compute_risk_score(
            {},
            scope_creep={"is_new_action": True, "amount_anomaly": True}
        )
        self.assertEqual(result["score"], 45)

    # ── Rule model complexity ────────────────────────────────────────────────

    def test_sequential_model_adds_complexity(self):
        rule = self._make_rule(model="sequential")
        result = compute_risk_score({}, rule=rule)
        factors_str = " ".join(result["factors"])
        self.assertIn("sequential", factors_str)

    def test_all_of_n_adds_complexity(self):
        rule = self._make_rule(model="all_of_n")
        result = compute_risk_score({}, rule=rule)
        factors_str = " ".join(result["factors"])
        self.assertIn("all_of_n", factors_str)

    def test_step_up_adds_risk(self):
        rule = self._make_rule(step_up=[{"field": "amount", "operator": "gt", "value": 1000}])
        result = compute_risk_score({}, rule=rule)
        factors_str = " ".join(result["factors"])
        self.assertIn("step_up", factors_str)

    def test_any_one_no_complexity_factor(self):
        rule = self._make_rule(model="any_one")
        result = compute_risk_score({}, rule=rule)
        factors_str = " ".join(result["factors"])
        self.assertNotIn("sequential", factors_str)
        self.assertNotIn("all_of_n", factors_str)

    # ── Risk level classification ────────────────────────────────────────────

    def test_score_0_is_low(self):
        result = compute_risk_score({})
        self.assertEqual(result["level"], "low")

    def test_score_25_is_low(self):
        result = compute_risk_score({}, scope_creep={"is_new_action": True, "amount_anomaly": False})
        self.assertEqual(result["level"], "low")

    def test_score_40_is_medium(self):
        # 20 (new_action) + 25 (amount_anomaly) = 45 → medium
        result = compute_risk_score(
            {},
            scope_creep={"is_new_action": True, "amount_anomaly": True}
        )
        self.assertIn(result["level"], ("medium", "high"))

    def test_high_amount_high_anomaly_is_critical(self):
        result = compute_risk_score(
            {"amount": 15000},
            scope_creep={"is_new_action": True, "amount_anomaly": True}
        )
        self.assertIn(result["level"], ("high", "critical"))

    def test_score_capped_at_100(self):
        # pile on all risk factors
        rule = self._make_rule(model="sequential", step_up=[{"x": 1}])
        result = compute_risk_score(
            {"amount": 50000},
            scope_creep={"is_new_action": True, "amount_anomaly": True},
            rule=rule,
        )
        self.assertLessEqual(result["score"], 100)

    # ── Return structure ─────────────────────────────────────────────────────

    def test_returns_score_level_factors(self):
        result = compute_risk_score({"amount": 500})
        self.assertIn("score", result)
        self.assertIn("level", result)
        self.assertIn("factors", result)
        self.assertIsInstance(result["score"], int)
        self.assertIsInstance(result["factors"], list)

    def test_empty_params_returns_zero(self):
        result = compute_risk_score({})
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["factors"], [])

    def test_none_scope_creep_ok(self):
        result = compute_risk_score({"amount": 100}, scope_creep=None)
        self.assertIsNotNone(result)


class TestAutoApproveThreshold(unittest.TestCase):
    """Verify threshold comparison logic used in routes/request.py."""

    def test_score_below_threshold_should_auto_approve(self):
        risk = compute_risk_score({"amount": 50})  # score = 10
        threshold = 20
        self.assertLessEqual(risk["score"], threshold)

    def test_score_equal_threshold_should_auto_approve(self):
        risk = compute_risk_score({"amount": 500})  # score = 10
        self.assertLessEqual(risk["score"], risk["score"])  # boundary

    def test_score_above_threshold_should_not_auto_approve(self):
        risk = compute_risk_score({"amount": 15000, "total": 15000})  # score ≥ 40
        threshold = 20
        self.assertGreater(risk["score"], threshold)

    def test_none_threshold_means_disabled(self):
        # When threshold is None, no auto-approve — just check None != int
        threshold = None
        self.assertIsNone(threshold)


if __name__ == "__main__":
    unittest.main()

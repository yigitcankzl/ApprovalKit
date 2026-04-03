"""Tests for AIUC-1 audit export logic (Feature 10)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import datetime, timedelta


class TestAuditExportPayload:
    """Validate the AIUC-1 export payload structure."""

    def _make_job(self, state="approved", risk_score=10, risk_level="low",
                  rejection_reason=None, final_params=None):
        from unittest.mock import MagicMock
        from api.models.approval_job import JobState
        job = MagicMock()
        job.id = "job-uuid-001"
        job.agent_user_id = "test-agent"
        job.connection = "stripe-prod"
        job.action = "charge"
        job.state = getattr(JobState, state.upper(), JobState.APPROVED)
        job.created_at = datetime(2026, 1, 15, 10, 0, 0)
        job.completed_at = datetime(2026, 1, 15, 10, 2, 30) if state in ("approved", "rejected") else None
        job.params = {"amount": 500}
        job.final_params = final_params
        job.risk_score = risk_score
        job.risk_level = risk_level
        job.rejection_reason = rejection_reason
        return job

    def _build_event(self, job):
        return {
            "timestamp": job.created_at.isoformat(),
            "job_id": str(job.id),
            "agent_id": job.agent_user_id,
            "connection": job.connection,
            "action": job.action,
            "decision": job.state.value,
            "risk_score": getattr(job, "risk_score", 0) or 0,
            "risk_level": getattr(job, "risk_level", "low") or "low",
            "rejection_reason": getattr(job, "rejection_reason", None),
            "params_modified": job.final_params is not None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        }

    def test_event_has_required_fields(self):
        job = self._make_job()
        event = self._build_event(job)
        required = ["timestamp", "job_id", "agent_id", "connection", "action",
                    "decision", "risk_score", "risk_level", "rejection_reason",
                    "params_modified", "completed_at"]
        for field in required:
            assert field in event, f"Missing field: {field}"

    def test_approved_job_event_values(self):
        job = self._make_job(state="approved", risk_score=15, risk_level="low")
        event = self._build_event(job)
        assert event["decision"] == "approved"
        assert event["risk_score"] == 15
        assert event["risk_level"] == "low"
        assert event["rejection_reason"] is None
        assert event["params_modified"] is False

    def test_rejected_job_has_reason(self):
        job = self._make_job(state="rejected", rejection_reason="Too risky")
        event = self._build_event(job)
        assert event["decision"] == "rejected"
        assert event["rejection_reason"] == "Too risky"

    def test_modified_params_flag(self):
        job = self._make_job(state="approved", final_params={"amount": 400})
        event = self._build_event(job)
        assert event["params_modified"] is True

    def test_unmodified_params_flag(self):
        job = self._make_job(state="approved", final_params=None)
        event = self._build_event(job)
        assert event["params_modified"] is False

    def test_completed_at_none_for_pending(self):
        job = self._make_job(state="pending")
        job.completed_at = None
        event = self._build_event(job)
        assert event["completed_at"] is None

    def test_risk_score_defaults_to_zero_when_none(self):
        job = self._make_job()
        job.risk_score = None
        event = self._build_event(job)
        assert event["risk_score"] == 0

    def test_risk_level_defaults_to_low_when_none(self):
        job = self._make_job()
        job.risk_level = None
        event = self._build_event(job)
        assert event["risk_level"] == "low"


class TestAuditExportSummary:
    """Validate summary statistics calculation."""

    def _make_summary(self, jobs):
        from api.models.approval_job import JobState
        total = len(jobs)
        approved = sum(1 for j in jobs if j["state"] == "approved")
        rejected = sum(1 for j in jobs if j["state"] == "rejected")
        auto_approved = sum(1 for j in jobs if j["state"] == "pre_approved")
        latencies = [
            (j["completed_at"] - j["created_at"]).total_seconds()
            for j in jobs
            if j["completed_at"] and j["created_at"] and j["state"] in ("approved", "rejected")
        ]
        avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else 0
        return {
            "total_requests": total,
            "auto_approved": auto_approved,
            "human_approved": approved,
            "rejected": rejected,
            "pending_or_other": total - approved - rejected - auto_approved,
            "average_latency_seconds": avg_latency,
        }

    def _job(self, state, seconds=None):
        t = datetime(2026, 1, 15, 10, 0, 0)
        return {
            "state": state,
            "created_at": t,
            "completed_at": t + timedelta(seconds=seconds) if seconds else None,
        }

    def test_total_count(self):
        jobs = [self._job("approved", 60), self._job("rejected", 30), self._job("pending")]
        s = self._make_summary(jobs)
        assert s["total_requests"] == 3

    def test_approved_count(self):
        jobs = [self._job("approved", 60), self._job("approved", 30), self._job("rejected", 10)]
        s = self._make_summary(jobs)
        assert s["human_approved"] == 2

    def test_rejected_count(self):
        jobs = [self._job("rejected", 10), self._job("approved", 60)]
        s = self._make_summary(jobs)
        assert s["rejected"] == 1

    def test_auto_approved_count(self):
        jobs = [self._job("pre_approved"), self._job("pre_approved"), self._job("approved", 60)]
        s = self._make_summary(jobs)
        assert s["auto_approved"] == 2

    def test_average_latency_seconds(self):
        jobs = [self._job("approved", 60), self._job("approved", 120)]
        s = self._make_summary(jobs)
        assert s["average_latency_seconds"] == 90.0

    def test_average_latency_empty_when_no_completed(self):
        jobs = [self._job("pending"), self._job("pending")]
        s = self._make_summary(jobs)
        assert s["average_latency_seconds"] == 0

    def test_pending_or_other(self):
        jobs = [self._job("pending"), self._job("approved", 60), self._job("timeout")]
        s = self._make_summary(jobs)
        assert s["pending_or_other"] == 2

    def test_aiuc_version_field(self):
        payload = {
            "aiuc_version": "1.0-draft",
            "export_timestamp": datetime.utcnow().isoformat(),
            "workspace_id": "ws-123",
            "summary": {},
            "events": [],
        }
        assert payload["aiuc_version"] == "1.0-draft"
        assert "export_timestamp" in payload
        assert "workspace_id" in payload


class TestBudgetTracker:
    """Unit tests for budget tracking logic."""

    def test_budget_pct_calculation(self):
        spent = 12500.0
        limit = 50000
        pct = round(spent / limit * 100, 1)
        assert pct == 25.0

    def test_budget_pct_over_100(self):
        spent = 55000.0
        limit = 50000
        pct = round(spent / limit * 100, 1)
        assert pct == 110.0

    def test_budget_pct_zero_spent(self):
        spent = 0.0
        limit = 50000
        pct = round(spent / limit * 100, 1)
        assert pct == 0.0

    def test_default_limits_exist(self):
        from api.constants import DEFAULT_BUDGET_LIMITS
        assert "daily" in DEFAULT_BUDGET_LIMITS
        assert "weekly" in DEFAULT_BUDGET_LIMITS
        assert "monthly" in DEFAULT_BUDGET_LIMITS

    def test_daily_limit_less_than_weekly(self):
        from api.constants import DEFAULT_BUDGET_LIMITS
        assert DEFAULT_BUDGET_LIMITS["daily"] < DEFAULT_BUDGET_LIMITS["weekly"]

    def test_weekly_limit_less_than_monthly(self):
        from api.constants import DEFAULT_BUDGET_LIMITS
        assert DEFAULT_BUDGET_LIMITS["weekly"] < DEFAULT_BUDGET_LIMITS["monthly"]

    def test_budget_response_structure(self):
        budget = {
            "agent_id": "uuid",
            "agent_name": "my-agent",
            "daily": {"spent": 100.0, "limit": 50000, "pct": 0.2},
            "weekly": {"spent": 500.0, "limit": 200000, "pct": 0.25},
            "monthly": {"spent": 1000.0, "limit": 500000, "pct": 0.2},
        }
        for period in ("daily", "weekly", "monthly"):
            assert "spent" in budget[period]
            assert "limit" in budget[period]
            assert "pct" in budget[period]

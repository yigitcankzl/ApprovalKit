"""Tests for denial feedback / rejection reason (Feature 4)."""

import sys
import os
_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _root)
# SDK may be at sdk/approvalkit/ (monorepo) or installed as package
_sdk_path = os.path.join(_root, "sdk", "approvalkit")
if os.path.isdir(_sdk_path):
    sys.path.insert(0, _sdk_path)

import pytest
from api.schemas.request import JobStatusResponse


class TestJobStatusResponseSchema:

    def test_rejection_reason_optional(self):
        r = JobStatusResponse(job_id="j1", status="rejected")
        assert r.rejection_reason is None

    def test_rejection_reason_populated(self):
        r = JobStatusResponse(
            job_id="j1",
            status="rejected",
            rejection_reason="Amount exceeds policy limit",
        )
        assert r.rejection_reason == "Amount exceeds policy limit"

    def test_retry_allowed_defaults_true(self):
        r = JobStatusResponse(job_id="j1", status="rejected")
        assert r.retry_allowed is True

    def test_retry_allowed_false_for_blocked(self):
        r = JobStatusResponse(job_id="j1", status="blocked", retry_allowed=False)
        assert r.retry_allowed is False

    def test_risk_score_defaults_zero(self):
        r = JobStatusResponse(job_id="j1", status="pending")
        assert r.risk_score == 0

    def test_risk_level_defaults_low(self):
        r = JobStatusResponse(job_id="j1", status="pending")
        assert r.risk_level == "low"

    def test_risk_score_populated(self):
        r = JobStatusResponse(job_id="j1", status="pending", risk_score=45, risk_level="medium")
        assert r.risk_score == 45
        assert r.risk_level == "medium"

    def test_full_response_structure(self):
        r = JobStatusResponse(
            job_id="abc-123",
            status="rejected",
            approvals_count=0,
            required_count=2,
            rejection_reason="Recipient not in approved list",
            retry_allowed=True,
            risk_score=30,
            risk_level="medium",
        )
        assert r.job_id == "abc-123"
        assert r.rejection_reason == "Recipient not in approved list"
        assert r.risk_score == 30


class TestApprovalDeniedError:

    def test_basic_construction(self):
        from sdk.approvalkit import ApprovalDenied
        err = ApprovalDenied("rejected")
        assert err.status == "rejected"
        assert err.job_id is None
        assert err.reason is None
        assert "rejected" in str(err)

    def test_with_job_id(self):
        from sdk.approvalkit import ApprovalDenied
        err = ApprovalDenied("timeout", job_id="job-999")
        assert err.job_id == "job-999"
        assert "job-999" in str(err)

    def test_with_reason(self):
        from sdk.approvalkit import ApprovalDenied
        err = ApprovalDenied("rejected", job_id="j1", reason="Policy violation: amount too high")
        assert err.reason == "Policy violation: amount too high"
        assert "Policy violation" in str(err)

    def test_reason_none_no_colon(self):
        from sdk.approvalkit import ApprovalDenied
        err = ApprovalDenied("rejected", job_id="j1", reason=None)
        assert ":" not in str(err) or "job=" in str(err)

    def test_reason_empty_string(self):
        from sdk.approvalkit import ApprovalDenied
        err = ApprovalDenied("rejected", job_id="j1", reason="")
        assert err.reason == ""

    def test_is_exception(self):
        from sdk.approvalkit import ApprovalDenied
        err = ApprovalDenied("blocked")
        assert isinstance(err, Exception)

    def test_blocked_status(self):
        from sdk.approvalkit import ApprovalDenied
        err = ApprovalDenied("blocked")
        assert err.status == "blocked"

    def test_timeout_status(self):
        from sdk.approvalkit import ApprovalDenied
        err = ApprovalDenied("timeout", job_id="j2")
        assert err.status == "timeout"
        assert err.job_id == "j2"


class TestApprovalKitSDKConfig:
    """Test SDK configuration — no network calls."""

    def test_default_base_url(self):
        import os
        os.environ.pop("APPROVALKIT_BASE_URL", None)
        from sdk.approvalkit import ApprovalKit
        kit = ApprovalKit()
        assert kit.base_url == "http://localhost:8000"

    def test_custom_base_url(self):
        from sdk.approvalkit import ApprovalKit
        kit = ApprovalKit(base_url="https://api.example.com/")
        assert kit.base_url == "https://api.example.com"  # trailing slash stripped

    def test_poll_interval_clamped(self):
        from sdk.approvalkit import ApprovalKit
        kit = ApprovalKit(poll_interval=0)
        assert kit.poll_interval >= 1
        kit2 = ApprovalKit(poll_interval=999)
        assert kit2.poll_interval <= 120

    def test_timeout_clamped(self):
        from sdk.approvalkit import ApprovalKit
        kit = ApprovalKit(timeout=5)
        assert kit.timeout >= 10
        kit2 = ApprovalKit(timeout=99999)
        assert kit2.timeout <= 3600

    def test_validate_inputs_empty_connection(self):
        from sdk.approvalkit import ApprovalKit
        kit = ApprovalKit()
        with pytest.raises(ValueError, match="connection"):
            kit._validate_inputs("", "charge", {})

    def test_validate_inputs_empty_action(self):
        from sdk.approvalkit import ApprovalKit
        kit = ApprovalKit()
        with pytest.raises(ValueError, match="action"):
            kit._validate_inputs("stripe", "", {})

    def test_validate_inputs_params_not_dict(self):
        from sdk.approvalkit import ApprovalKit
        kit = ApprovalKit()
        with pytest.raises(TypeError):
            kit._validate_inputs("stripe", "charge", "not-a-dict")

    def test_hmac_sign_produces_hex(self):
        import re
        from sdk.approvalkit import ApprovalKit
        kit = ApprovalKit(hmac_secret="my-secret", api_key="my-key")
        ts, sig = kit._sign('{"test": 1}')
        assert re.match(r"^\d+$", ts)
        assert re.match(r"^[0-9a-f]{64}$", sig)

    def test_hmac_sign_different_body_different_sig(self):
        from sdk.approvalkit import ApprovalKit
        kit = ApprovalKit(hmac_secret="my-secret", api_key="my-key")
        _, sig1 = kit._sign('{"amount": 100}')
        _, sig2 = kit._sign('{"amount": 200}')
        assert sig1 != sig2

    def test_headers_structure(self):
        from sdk.approvalkit import ApprovalKit
        kit = ApprovalKit(api_key="test-key", hmac_secret="test-secret")
        headers = kit._headers("12345", "abc123def456")
        assert headers["Authorization"] == "Bearer test-key"
        assert headers["X-Signature"].startswith("hmac-sha256=")
        assert "Content-Type" in headers

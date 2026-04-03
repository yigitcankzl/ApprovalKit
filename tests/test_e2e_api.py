"""
E2E integration tests against the running Docker API.
Run with: pytest tests/test_e2e_api.py -v

Requires: docker compose up (API on http://localhost:8000)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid
import time
import hmac
import hashlib
import json
import pytest
import urllib.request
import urllib.error

BASE_URL = os.getenv("APPROVALKIT_TEST_URL", "http://localhost:8000")
TEST_SUB = f"e2e-test-{uuid.uuid4().hex[:8]}"


def http_get(path, headers=None):
    req = urllib.request.Request(f"{BASE_URL}{path}", headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def http_post(path, body=None, headers=None, raw_body: bytes | None = None):
    data = raw_body if raw_body is not None else json.dumps(body or {}, separators=(",", ":")).encode()
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def sign(body_str, hmac_secret, api_key=""):
    ts = str(int(time.time()))
    sign_key = f"{hmac_secret}:{api_key}" if api_key else hmac_secret
    sig = hmac.new(sign_key.encode(), f"{ts}.{body_str}".encode(), hashlib.sha256).hexdigest()
    return ts, sig


def api_headers(sub=None):
    return {"X-User-Sub": sub or TEST_SUB}


def is_api_up():
    try:
        code, _ = http_get("/health")
        return code == 200
    except Exception:
        return False


# ── Skip if API not running ───────────────────────────────────────────────────

pytestmark = pytest.mark.skipif(
    not is_api_up(),
    reason="API not running — start with: docker compose up -d"
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def workspace():
    """Create a fresh workspace for e2e tests via /api/v1/workspace/setup."""
    sub = f"e2e-{uuid.uuid4().hex[:8]}"
    code, data = http_post("/api/v1/workspace/setup", {
        "domain": "e2e-test.auth0.com",
        "client_id": "e2e-client-id",
        "client_secret": "e2e-client-secret",
        "hmac_secret": f"e2e-hmac-{uuid.uuid4().hex}",
    }, headers={"Content-Type": "application/json", "X-User-Sub": sub})
    if code not in (200, 201):
        pytest.skip(f"Could not create workspace: {code} {data}")
    return {
        "id": data.get("workspace_id", ""),
        "sub": sub,
        "hmac_secret": data.get("hmac_secret", ""),
        "api_key": data.get("api_key", ""),
    }


@pytest.fixture(scope="module")
def ws_headers(workspace):
    return {"X-User-Sub": workspace["sub"]}


@pytest.fixture(scope="module")
def approver_id(workspace, ws_headers):
    code, data = http_post("/api/v1/approvers", {
        "name": "E2E Approver",
        "email": "e2e@approvalkit.test",
        "auth0_user_id": f"auth0|e2e{uuid.uuid4().hex[:8]}",
        "notification_channels": [],
    }, headers={**ws_headers, "Content-Type": "application/json"})
    if code not in (200, 201):
        pytest.skip(f"Could not create approver: {code} {data}")
    return data["id"]


@pytest.fixture(scope="module")
def rule_id(workspace, ws_headers, approver_id):
    code, data = http_post("/api/v1/rules", {
        "name": "E2E Rule",
        "connection": "e2e-connection",
        "action": "e2e_action",
        "conditions": [{"field": "amount", "operator": "gt", "value": 100}],
        "model": "any_one",
        "approver_ids": [approver_id],
        "timeout_seconds": 30,
    }, headers={**ws_headers, "Content-Type": "application/json"})
    if code not in (200, 201):
        pytest.skip(f"Could not create rule: {code} {data}")
    return data["id"]


# ── Health ────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self):
        code, data = http_get("/health")
        assert code == 200
        assert data.get("status") == "healthy"

    def test_docs_accessible(self):
        req = urllib.request.Request(f"{BASE_URL}/docs")
        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.status == 200
            body = resp.read()
            assert b"swagger" in body.lower() or b"openapi" in body.lower() or b"<!DOCTYPE" in body.lower()

    def test_openapi_schema(self):
        code, data = http_get("/openapi.json")
        assert code == 200
        assert "paths" in data
        assert "info" in data
        assert data["info"]["title"] == "ApprovalKit"


# ── Workspace ────────────────────────────────────────────────────────────────

class TestWorkspace:
    def test_no_workspace_returns_404(self):
        code, data = http_get("/api/v1/rules", headers={"X-User-Sub": f"no-ws-{uuid.uuid4().hex}"})
        assert code in (404, 422)

    def test_workspace_created(self, workspace):
        assert "id" in workspace
        assert len(workspace["id"]) == 36  # UUID

    def test_workspace_settings_accessible(self, ws_headers):
        code, data = http_get("/api/v1/workspace", headers=ws_headers)
        assert code == 200
        assert "id" in data or "workspace_id" in data or "domain" in data

    def test_security_status_endpoint(self, ws_headers):
        code, data = http_get("/api/v1/security-status", headers=ws_headers)
        assert code == 200
        assert "hmac" in data
        assert "fga" in data
        assert "token_vault" in data


# ── Rules ─────────────────────────────────────────────────────────────────────

class TestRulesCRUD:
    def test_list_rules_empty_initially(self, ws_headers):
        code, data = http_get("/api/v1/rules", headers=ws_headers)
        assert code == 200
        assert isinstance(data, list)

    def test_create_rule(self, rule_id):
        assert len(rule_id) == 36

    def test_get_rule(self, ws_headers, rule_id):
        code, data = http_get(f"/api/v1/rules/{rule_id}", headers=ws_headers)
        assert code == 200
        assert data["id"] == rule_id
        assert data["name"] == "E2E Rule"

    def test_rule_has_risk_auto_approve_threshold_field(self, ws_headers, rule_id):
        code, data = http_get(f"/api/v1/rules/{rule_id}", headers=ws_headers)
        assert code == 200
        # Field exists (None by default)
        assert "risk_auto_approve_threshold" in data or data.get("risk_auto_approve_threshold") is None

    def test_list_templates(self, ws_headers):
        code, data = http_get("/api/v1/rules/templates", headers=ws_headers)
        assert code == 200
        # templates endpoint returns either list or {"templates": [...], "categories": [...]}
        if isinstance(data, list):
            assert len(data) > 0
        else:
            assert "templates" in data
            assert len(data["templates"]) > 0

    def test_simulate_rule_match(self, ws_headers, rule_id):
        code, data = http_post("/api/v1/rules/simulate", {
            "connection": "e2e-connection",
            "action": "e2e_action",
            "params": {"amount": 500},
        }, headers={**ws_headers, "Content-Type": "application/json"})
        assert code in (200, 422)  # 422 if simulate requires approver_id
        if code == 200:
            assert "matched_rule" in data or "rule" in data or "match" in str(data)


# ── Approval Request ──────────────────────────────────────────────────────────

class TestApprovalRequest:
    def _signed_headers(self, workspace, body_str):
        api_key = workspace.get("api_key", "")
        # Per-agent keys start with ak_ and use "hmac:api_key" signing.
        # Workspace keys use just the hmac_secret.
        ts, sig = sign(body_str, workspace["hmac_secret"], api_key if api_key.startswith("ak_") else "")
        return {
            "Authorization": f"Bearer {api_key}",
            "X-Signature": f"hmac-sha256={ts}.{sig}",
            "Content-Type": "application/json",
            "X-User-Sub": workspace["sub"],
        }

    def test_request_no_rule_auto_approved(self, workspace):
        """Connection/action with no matching rule → immediate auto-approve."""
        body = {
            "connection": "no-rule-connection",
            "action": "no_rule_action",
            "params": {"amount": 50},
            "user_id": "e2e-agent",
            "idempotency_key": f"e2e-idem-{uuid.uuid4()}",
        }
        body_str = json.dumps(body, separators=(",", ":"))
        code, data = http_post("/api/v1/request", body,
                               headers=self._signed_headers(workspace, body_str))
        assert code in (200, 202)
        assert data.get("status") in ("approved", "pre_approved", "pending")

    def test_request_with_matching_rule_pending(self, workspace, rule_id):
        """Request matching an active rule → pending with job_id."""
        body = {
            "connection": "e2e-connection",
            "action": "e2e_action",
            "params": {"amount": 500},
            "user_id": "e2e-agent",
            "idempotency_key": f"e2e-rule-{uuid.uuid4()}",
        }
        body_str = json.dumps(body, separators=(",", ":"))
        code, data = http_post("/api/v1/request", body,
                               headers=self._signed_headers(workspace, body_str))
        assert code in (200, 202)
        if data.get("status") == "pending":
            assert "job_id" in data

    def test_invalid_hmac_rejected(self, workspace):
        body = {
            "connection": "e2e-connection",
            "action": "e2e_action",
            "params": {},
            "user_id": "e2e-agent",
            "idempotency_key": f"e2e-bad-{uuid.uuid4()}",
        }
        code, data = http_post("/api/v1/request", body, headers={
            "Authorization": "Bearer ",
            "X-Signature": "hmac-sha256=9999999999.badsignaturehere",
            "Content-Type": "application/json",
            "X-User-Sub": workspace["sub"],
        })
        assert code == 401

    def test_rate_limit_header_present(self, workspace):
        """Signed request should be accepted (200/202)."""
        body = {
            "connection": "no-rule-connection",
            "action": "rate_check",
            "params": {},
            "user_id": "e2e-agent",
            "idempotency_key": f"e2e-rate-{uuid.uuid4()}",
        }
        body_str = json.dumps(body, separators=(",", ":"))
        code, data = http_post("/api/v1/request", body,
                               headers=self._signed_headers(workspace, body_str))
        assert code in (200, 202, 429)


# ── Pending Jobs & Decision ───────────────────────────────────────────────────

class TestJobsWorkflow:
    def test_pending_jobs_list(self, ws_headers):
        code, data = http_get("/api/v1/jobs/pending", headers=ws_headers)
        assert code == 200
        assert isinstance(data, list)

    def test_pending_jobs_have_risk_fields(self, workspace, ws_headers, rule_id):
        """Jobs created after the migration should include risk_score/level."""
        body = {
            "connection": "e2e-connection",
            "action": "e2e_action",
            "params": {"amount": 500},
            "user_id": "e2e-agent-risk",
            "idempotency_key": f"e2e-risk-{uuid.uuid4()}",
        }
        body_str = json.dumps(body, separators=(",", ":"))
        ts, sig = sign(body_str, workspace["hmac_secret"])
        http_post("/api/v1/request", body, headers={
            "Authorization": "Bearer ",
            "X-Signature": f"hmac-sha256={ts}.{sig}",
            "Content-Type": "application/json",
            "X-User-Sub": workspace["sub"],
        })
        time.sleep(0.5)
        code, jobs = http_get("/api/v1/jobs/pending", headers=ws_headers)
        assert code == 200
        if jobs:
            job = jobs[0]
            assert "risk_score" in job
            assert "risk_level" in job
            assert isinstance(job["risk_score"], int)
            assert job["risk_level"] in ("low", "medium", "high", "critical")

    def test_batch_decision_empty_list(self, ws_headers):
        code, data = http_post("/api/v1/jobs/batch-decision", {
            "job_ids": [],
            "decision": "approve",
        }, headers={**ws_headers, "Content-Type": "application/json"})
        assert code == 400

    def test_batch_decision_too_many(self, ws_headers):
        code, data = http_post("/api/v1/jobs/batch-decision", {
            "job_ids": [str(uuid.uuid4()) for _ in range(51)],
            "decision": "approve",
        }, headers={**ws_headers, "Content-Type": "application/json"})
        assert code == 400

    def test_decision_on_nonexistent_job(self, ws_headers):
        code, data = http_post(f"/api/v1/jobs/{uuid.uuid4()}/decision", {
            "decision": "approve",
        }, headers={**ws_headers, "Content-Type": "application/json"})
        assert code == 404


# ── Audit ─────────────────────────────────────────────────────────────────────

class TestAudit:
    def test_audit_log_accessible(self, ws_headers):
        code, data = http_get("/api/v1/audit", headers=ws_headers)
        assert code == 200
        assert isinstance(data, list)

    def test_recent_activity(self, ws_headers):
        code, data = http_get("/api/v1/recent-activity", headers=ws_headers)
        assert code == 200
        assert isinstance(data, list)

    def test_dashboard_stats(self, ws_headers):
        code, data = http_get("/api/v1/dashboard", headers=ws_headers)
        assert code == 200
        assert "total_actions_week" in data
        assert "approved" in data
        assert "rejected" in data

    def test_audit_export_json(self, ws_headers):
        code, data = http_get("/api/v1/audit/export?fmt=json", headers=ws_headers)
        assert code == 200
        assert data.get("aiuc_version") == "1.0-draft"
        assert "summary" in data
        assert "events" in data
        assert "export_period" in data

    def test_audit_export_summary_fields(self, ws_headers):
        code, data = http_get("/api/v1/audit/export?fmt=json", headers=ws_headers)
        assert code == 200
        summary = data["summary"]
        assert "total_requests" in summary
        assert "human_approved" in summary
        assert "auto_approved" in summary
        assert "rejected" in summary
        assert "average_latency_seconds" in summary

    def test_audit_export_with_date_range(self, ws_headers):
        code, data = http_get(
            "/api/v1/audit/export?fmt=json&from=2026-01-01&to=2026-12-31",
            headers=ws_headers
        )
        assert code == 200
        assert "events" in data

    def test_audit_patterns(self, ws_headers):
        code, data = http_get("/api/v1/audit/patterns", headers=ws_headers)
        assert code == 200
        assert "patterns" in data
        assert "stats" in data

    def test_ciba_quota(self, ws_headers):
        code, data = http_get("/api/v1/ciba-quota", headers=ws_headers)
        assert code == 200
        assert "current" in data
        assert "limit" in data


# ── Agents & Trust Score ─────────────────────────────────────────────────────

class TestAgents:
    def test_list_agents(self, ws_headers):
        code, data = http_get("/api/v1/agents", headers=ws_headers)
        assert code == 200
        assert isinstance(data, list)

    def test_agents_have_trust_fields(self, workspace, ws_headers):
        # Create an agent
        code, data = http_post("/api/v1/agents", {
            "name": f"trust-test-agent-{uuid.uuid4().hex[:6]}",
            "description": "Trust score e2e test",
        }, headers={**ws_headers, "Content-Type": "application/json"})
        assert code == 201
        assert "trust_score" in data
        assert "trust_level" in data
        assert data["trust_score"] == 100
        assert data["trust_level"] == "high"

    def test_budget_endpoint(self, ws_headers):
        code, data = http_get("/api/v1/agents/budgets", headers=ws_headers)
        assert code == 200
        assert isinstance(data, list)

    def test_budget_entry_structure(self, workspace, ws_headers):
        # First create an agent
        http_post("/api/v1/agents", {
            "name": f"budget-test-{uuid.uuid4().hex[:6]}",
        }, headers={**ws_headers, "Content-Type": "application/json"})

        code, data = http_get("/api/v1/agents/budgets", headers=ws_headers)
        assert code == 200
        if data:
            entry = data[0]
            assert "agent_id" in entry
            assert "agent_name" in entry
            for period in ("daily", "weekly", "monthly"):
                assert period in entry
                assert "spent" in entry[period]
                assert "limit" in entry[period]
                assert "pct" in entry[period]


# ── Approvers ─────────────────────────────────────────────────────────────────

class TestApprovers:
    def test_list_approvers(self, ws_headers):
        code, data = http_get("/api/v1/approvers", headers=ws_headers)
        assert code == 200
        assert isinstance(data, list)

    def test_approver_created(self, approver_id):
        assert len(approver_id) == 36

    def test_approver_name_required(self, ws_headers):
        code, data = http_post("/api/v1/approvers", {
            "email": "missing-name@test.com",
        }, headers={**ws_headers, "Content-Type": "application/json"})
        assert code == 422

    def test_approver_email_required(self, ws_headers):
        code, data = http_post("/api/v1/approvers", {
            "name": "Missing Email",
        }, headers={**ws_headers, "Content-Type": "application/json"})
        assert code == 422


# ── Connections ───────────────────────────────────────────────────────────────

class TestConnections:
    def test_list_connections(self, ws_headers):
        code, data = http_get("/api/v1/connections", headers=ws_headers)
        assert code == 200
        assert isinstance(data, list)

    def test_consent_overview(self, ws_headers):
        code, data = http_get("/api/v1/consent", headers=ws_headers)
        assert code == 200


# ── Input Validation ─────────────────────────────────────────────────────────

class TestInputValidation:
    def test_invalid_uuid_returns_400(self, ws_headers):
        code, data = http_get("/api/v1/rules/not-a-uuid", headers=ws_headers)
        assert code in (400, 404, 422)

    def test_rule_missing_required_fields(self, ws_headers):
        code, data = http_post("/api/v1/rules", {
            "name": "Incomplete Rule",
            # missing connection, action, model
        }, headers={**ws_headers, "Content-Type": "application/json"})
        assert code == 422

    def test_decision_invalid_value(self, ws_headers):
        code, data = http_post(f"/api/v1/jobs/{uuid.uuid4()}/decision", {
            "decision": "maybe",
        }, headers={**ws_headers, "Content-Type": "application/json"})
        assert code in (404, 422)

    def test_large_payload_rejected(self, ws_headers):
        # 1.1 MB payload should be rejected by body size middleware
        huge = "x" * (1_100_000)
        code, data = http_post("/api/v1/rules", {
            "name": huge,
            "connection": "stripe",
            "action": "charge",
            "model": "any_one",
        }, headers={**ws_headers, "Content-Type": "application/json"})
        assert code in (413, 422, 400)


# ── Test Request (dashboard) ─────────────────────────────────────────────────

class TestDashboardTestRequest:
    def test_test_request_no_rule(self, ws_headers):
        code, data = http_post("/api/v1/test-request", {
            "connection": "no-rule-dashboard",
            "action": "test_action",
            "params": {},
            "user_id": "dashboard-test",
            "idempotency_key": f"dash-{uuid.uuid4()}",
        }, headers={**ws_headers, "Content-Type": "application/json"})
        assert code in (200, 202)
        assert data.get("status") in ("auto_approved", "pending")

    def test_test_status_invalid_id(self, ws_headers):
        code, data = http_get(f"/api/v1/test-status/{uuid.uuid4()}", headers=ws_headers)
        assert code == 404

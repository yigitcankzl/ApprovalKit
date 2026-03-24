#!/usr/bin/env python3
"""
Demo: DevOps Agent
Simulates an AI agent that manages GitHub deployments through ApprovalKit.

Scenarios:
1. Deploy to staging        → auto-approve (no rule on staging)
2. Deploy to production     → any-one maintainer approval
3. Deploy at 23:30          → blackout window → hard blocked
4. Rollback production      → specific: lead engineer only
5. FGA demo                 → approver sees only own history, admin sees all
"""

import hmac
import hashlib
import json
import time
import uuid

import requests

API_URL = "http://localhost:8000"
API_KEY = "demo-devops-api-key"
HMAC_SECRET = "demo-hmac-secret"


def sign_request(payload: dict) -> dict:
    timestamp = str(int(time.time()))
    body = json.dumps(payload, separators=(",", ":"))
    message = f"{timestamp}.{body}"
    sig = hmac.new(HMAC_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
    return {
        "Authorization": f"Bearer {API_KEY}",
        "X-Signature": f"hmac-sha256={timestamp}.{sig}",
        "Content-Type": "application/json",
    }


def submit_request(connection: str, action: str, params: dict) -> dict:
    payload = {
        "connection": connection,
        "action": action,
        "params": params,
        "user_id": "auth0|devops-agent-001",
        "idempotency_key": str(uuid.uuid4()),
    }
    headers = sign_request(payload)
    response = requests.post(f"{API_URL}/api/v1/request", json=payload, headers=headers)
    return {"status_code": response.status_code, "body": response.json()}


def run_demo():
    print("=" * 60)
    print("  ApprovalKit Demo — DevOps Agent")
    print("=" * 60)

    # Scenario 1: Staging deploy — auto-approve
    print("\n--- Scenario 1: Deploy to staging ---")
    result = submit_request("github-main", "deploy", {"env": "staging", "branch": "feature/new-ui"})
    print(f"  Status: {result['status_code']} — {result['body'].get('status', 'error')}")
    print(f"  Expected: 200 OK (auto-approve, no rule for staging)")

    # Scenario 2: Production deploy — any-one maintainer
    print("\n--- Scenario 2: Deploy to production ---")
    result = submit_request("github-main", "deploy", {"env": "production", "branch": "main"})
    print(f"  Status: {result['status_code']} — {result['body'].get('status', 'error')}")
    print(f"  Expected: 202 Accepted (any-one maintainer approves)")
    if result["body"].get("job_id"):
        print(f"  Job ID: {result['body']['job_id']}")

    # Scenario 3: Production deploy during blackout
    print("\n--- Scenario 3: Deploy at 23:30 (blackout) ---")
    result = submit_request("github-main", "deploy", {"env": "production", "branch": "hotfix", "time": "23:30"})
    print(f"  Status: {result['status_code']} — {result['body'].get('status', 'error')}")
    print(f"  Expected: 403 Forbidden (blackout window 23:00-06:00)")

    # Scenario 4: Rollback — specific lead only
    print("\n--- Scenario 4: Rollback production ---")
    result = submit_request("github-main", "rollback", {"env": "production", "version": "v2.3.1"})
    print(f"  Status: {result['status_code']} — {result['body'].get('status', 'error')}")
    print(f"  Expected: 202 Accepted (specific: lead engineer, 2min timeout)")

    # Scenario 5: FGA access control demo
    print("\n--- Scenario 5: FGA Access Control ---")
    print("  Approver logs into dashboard → sees only their own approval history")
    print("  Admin logs into dashboard    → sees full audit log across all approvers")
    print("  FGA enforces this at the data layer, not just the UI")
    print()
    print("  FGA roles:")
    print("    workspace_admin  → Full access")
    print("    approver         → Own history only")
    print("    agent_owner      → Own agent only")
    print("    viewer           → Summary dashboard only")

    print("\n" + "=" * 60)
    print("  Demo complete — check dashboard for results")
    print("=" * 60)


if __name__ == "__main__":
    run_demo()

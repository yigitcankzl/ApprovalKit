#!/usr/bin/env python3
"""
Demo: E-commerce Agent
Simulates an AI agent that processes Stripe transactions through ApprovalKit.

Scenarios:
1. Purchase $30  → auto-approve (no matching rule)
2. Purchase $150 → CS approval via CIBA
3. Refund $340   → partial approval ($200 only)
4. Purchase $800 → CS + CFO sequential, CFO timeout → escalation to CEO
5. Agent tries stripe:payout (first time) → scope creep detected
"""

import hmac
import hashlib
import json
import time
import uuid
import sys

import requests

API_URL = "http://localhost:8000"
API_KEY = "demo-ecommerce-api-key"
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
        "user_id": "auth0|ecommerce-agent-001",
        "idempotency_key": str(uuid.uuid4()),
    }
    headers = sign_request(payload)
    response = requests.post(f"{API_URL}/api/v1/request", json=payload, headers=headers)
    return {"status_code": response.status_code, "body": response.json()}


def poll_status(job_id: str) -> dict:
    payload = {}
    headers = sign_request(payload)
    response = requests.get(f"{API_URL}/api/v1/status/{job_id}", headers=headers)
    return response.json()


def run_demo():
    print("=" * 60)
    print("  ApprovalKit Demo — E-commerce Agent")
    print("=" * 60)

    # Scenario 1: Small purchase — auto-approve
    print("\n--- Scenario 1: Purchase $30 ---")
    result = submit_request("stripe-prod", "charge", {"amount": 30, "customer": "alice@example.com"})
    print(f"  Status: {result['status_code']} — {result['body'].get('status', 'error')}")
    print(f"  Expected: 200 OK (auto-approve, no matching rule)")

    # Scenario 2: Medium purchase — CS approval
    print("\n--- Scenario 2: Purchase $150 ---")
    result = submit_request("stripe-prod", "charge", {"amount": 150, "customer": "bob@example.com"})
    print(f"  Status: {result['status_code']} — {result['body'].get('status', 'error')}")
    print(f"  Expected: 202 Accepted (CS receives Guardian push)")
    if result["body"].get("job_id"):
        print(f"  Job ID: {result['body']['job_id']}")
        print(f"  Poll: GET /api/v1/status/{result['body']['job_id']}")

    # Scenario 3: Refund with partial approval
    print("\n--- Scenario 3: Refund $340 ---")
    result = submit_request("stripe-prod", "refund", {"amount": 340, "order_id": "ORD-1234"})
    print(f"  Status: {result['status_code']} — {result['body'].get('status', 'error')}")
    print(f"  Expected: 202 Accepted (CS partial approval: $200 only)")

    # Scenario 4: Large purchase — sequential approval + escalation
    print("\n--- Scenario 4: Purchase $800 ---")
    result = submit_request("stripe-prod", "charge", {"amount": 800, "customer": "charlie@example.com"})
    print(f"  Status: {result['status_code']} — {result['body'].get('status', 'error')}")
    print(f"  Expected: 202 Accepted (CS → CFO sequential, timeout → CEO escalation)")

    # Scenario 5: Scope creep — first-time payout
    print("\n--- Scenario 5: Payout $1200 (scope creep) ---")
    result = submit_request("stripe-prod", "payout", {"amount": 1200, "recipient": "vendor@example.com"})
    print(f"  Status: {result['status_code']} — {result['body'].get('status', 'error')}")
    print(f"  Expected: Scope creep flagged in audit log")

    print("\n" + "=" * 60)
    print("  Demo complete — check dashboard for results")
    print("=" * 60)


if __name__ == "__main__":
    run_demo()

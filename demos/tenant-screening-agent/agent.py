"""
Demo Agent — Tenant Screening (Real Estate)
============================================
Simulates an AI agent that processes tenant background checks
with escalating approval for sensitive data sources.

Rule configuration:

  screening-svc : tenant_check
    type=credit_check        -> no rule  (auto-approved)
    type=eviction_history    -> any_one  [property_manager]
    type=criminal_check      -> all_of_n [property_manager, legal]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/tenant-screening-agent/agent.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sdk"))

from approvalkit import ApprovalKit, ApprovalDenied

kit = ApprovalKit(
    base_url=os.environ.get("APPROVALKIT_URL", "http://localhost:8000"),
    api_key=os.environ.get("APPROVALKIT_API_KEY", ""),
    hmac_secret=os.environ.get("APPROVALKIT_HMAC_SECRET", ""),
    user_id="auth0|tenant_screening_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

APPLICANTS = {
    "TEN-8001": {
        "name": "David Kim",
        "email": "david.kim@example.com",
        "income_usd": 72000,
        "desired_unit": "Apt 4C, Maple Heights",
    },
    "TEN-8002": {
        "name": "Sarah Johnson",
        "email": "s.johnson@example.com",
        "income_usd": 58000,
        "desired_unit": "Unit 7, Cedar Flats",
    },
    "TEN-8003": {
        "name": "Robert Novak",
        "email": "r.novak@example.com",
        "income_usd": 95000,
        "desired_unit": "Suite 2A, Birch Tower",
    },
}

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="screening-svc",
    action="tenant_check",
    params_fn=lambda applicant_id: {
        "applicant_id": applicant_id,
        "applicant_name": APPLICANTS[applicant_id]["name"],
        "income_usd": APPLICANTS[applicant_id]["income_usd"],
        "desired_unit": APPLICANTS[applicant_id]["desired_unit"],
        "type": "credit_check",
    },
)
def run_credit_check(applicant_id: str) -> dict:
    """
    Run a standard credit check on a tenant applicant.
    Auto-approved -- standard pre-screening step.
    """
    applicant = APPLICANTS[applicant_id]
    return {
        "applicant": applicant["name"],
        "credit_score": 742,
        "debt_to_income": 0.28,
        "status": "credit_check_complete",
    }


@kit.requires_approval(
    connection="screening-svc",
    action="tenant_check",
    params_fn=lambda applicant_id, reason: {
        "applicant_id": applicant_id,
        "applicant_name": APPLICANTS[applicant_id]["name"],
        "desired_unit": APPLICANTS[applicant_id]["desired_unit"],
        "type": "eviction_history",
        "reason": reason,
    },
)
def check_eviction_history(applicant_id: str, reason: str) -> dict:
    """
    Query eviction records for a tenant applicant.
    Requires property_manager approval due to sensitive data.
    """
    applicant = APPLICANTS[applicant_id]
    return {
        "applicant": applicant["name"],
        "eviction_records": 0,
        "status": "eviction_check_clear",
    }


@kit.requires_approval(
    connection="screening-svc",
    action="tenant_check",
    params_fn=lambda applicant_id, reason: {
        "applicant_id": applicant_id,
        "applicant_name": APPLICANTS[applicant_id]["name"],
        "desired_unit": APPLICANTS[applicant_id]["desired_unit"],
        "type": "criminal_check",
        "reason": reason,
    },
)
def run_criminal_check(applicant_id: str, reason: str) -> dict:
    """
    Run a criminal background check.
    Requires both property_manager AND legal approval (all_of_n).
    """
    applicant = APPLICANTS[applicant_id]
    return {
        "applicant": applicant["name"],
        "criminal_records": 0,
        "status": "criminal_check_clear",
    }


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Tenant Screening Agent Demo")
    print("="*60)

    # -- Scenario 1: Credit check -- auto-approved ---
    scenario("Scenario 1: Credit check -- auto-approved")
    try:
        result = run_credit_check("TEN-8001")
        print(f"  Applicant: {result['applicant']}")
        print(f"  Credit score: {result['credit_score']}")
        print(f"  Debt-to-income: {result['debt_to_income']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 2: Eviction history -- property_manager ---
    scenario("Scenario 2: Eviction history check -- property_manager approval")
    try:
        result = check_eviction_history(
            "TEN-8002",
            "Standard screening for Cedar Flats applicant"
        )
        print(f"  Applicant: {result['applicant']}")
        print(f"  Eviction records found: {result['eviction_records']}")
        print(f"  Status: {result['status']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 3: Criminal check -- property_manager + legal ---
    scenario("Scenario 3: Criminal check -- property_manager + legal required")
    print("  Both property_manager and legal must approve.")
    try:
        result = run_criminal_check(
            "TEN-8003",
            "High-value commercial unit; enhanced screening policy"
        )
        print(f"  Applicant: {result['applicant']}")
        print(f"  Criminal records found: {result['criminal_records']}")
        print(f"  Status: {result['status']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

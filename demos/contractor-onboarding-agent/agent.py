"""
Demo Agent -- Contractor Onboarding
=====================================
Simulates an AI agent that onboards external contractors by sending
NDAs, processing payment agreements, handling large contracts, and
provisioning repository access. Each step is gated via ApprovalKit.

Rule configuration (set up via dashboard or setup_rules.py):

  gmail-prod : send_nda
    any contractor         -> no rule  (auto-approved)

  gmail-prod : payment_agreement
    any contractor         -> specific [legal_counsel]

  gmail-prod : large_contract
    value >= $50k          -> all_of_n [legal_counsel, ceo]

  github-prod : repo_access
    any contractor         -> specific [manager]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/contractor-onboarding-agent/agent.py
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
    user_id="auth0|contractor_onboarding_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

CONTRACTORS = [
    {"name": "Freelance Dev Co", "contact": "julia@freelancedev.co", "type": "development", "rate_hourly": 150},
    {"name": "DataWorks LLC", "contact": "info@dataworks.io", "type": "data_engineering", "rate_hourly": 200},
    {"name": "SecureAudit Partners", "contact": "contracts@secureaudit.com", "type": "security_audit", "rate_hourly": 350},
]

CONTRACT_TEMPLATES = {
    "standard_nda": {"duration_months": 24, "scope": "Confidential company information"},
    "mutual_nda": {"duration_months": 36, "scope": "Bidirectional IP and trade secrets"},
}

PROJECTS = [
    {"name": "Mobile App Redesign", "duration_months": 3, "budget": 45000, "repos": ["mobile-app", "design-system"]},
    {"name": "Data Pipeline Migration", "duration_months": 6, "budget": 120000, "repos": ["etl-pipeline", "data-warehouse"]},
    {"name": "Annual Security Audit", "duration_months": 2, "budget": 85000, "repos": ["infrastructure", "security-configs"]},
]

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="gmail-prod",
    action="send_nda",
    params_fn=lambda contractor_name, contact_email, nda_type, duration_months, scope: {
        "contractor_name": contractor_name,
        "contact_email": contact_email,
        "nda_type": nda_type,
        "duration_months": duration_months,
        "scope": scope,
    },
)
def send_nda(contractor_name: str, contact_email: str, nda_type: str,
             duration_months: int, scope: str) -> dict:
    """
    Send NDA to contractor via Gmail.
    Auto-approved -- standard onboarding step.
    """
    return {"nda_sent": True, "contractor": contractor_name, "type": nda_type}


@kit.requires_approval(
    connection="gmail-prod",
    action="payment_agreement",
    params_fn=lambda contractor_name, contact_email, project, rate_hourly, estimated_hours, total_budget: {
        "contractor_name": contractor_name,
        "contact_email": contact_email,
        "project": project,
        "rate_hourly_usd": rate_hourly,
        "estimated_hours": estimated_hours,
        "total_budget_usd": total_budget,
    },
)
def send_payment_agreement(contractor_name: str, contact_email: str,
                           project: str, rate_hourly: int,
                           estimated_hours: int, total_budget: int) -> dict:
    """
    Send payment agreement with rate and budget terms.
    Requires Legal Counsel approval.
    """
    return {"agreement_sent": True, "contractor": contractor_name, "budget": total_budget}


@kit.requires_approval(
    connection="gmail-prod",
    action="large_contract",
    params_fn=lambda contractor_name, contact_email, project, total_value, duration_months, deliverables: {
        "contractor_name": contractor_name,
        "contact_email": contact_email,
        "project": project,
        "total_value_usd": total_value,
        "duration_months": duration_months,
        "deliverables": deliverables,
    },
)
def execute_large_contract(contractor_name: str, contact_email: str,
                           project: str, total_value: int,
                           duration_months: int, deliverables: str) -> dict:
    """
    Execute a large contract (>=$50k).
    Requires both Legal Counsel and CEO approval (all_of_n).
    """
    return {"contract_executed": True, "contractor": contractor_name, "value": total_value}


@kit.requires_approval(
    connection="github-prod",
    action="repo_access",
    params_fn=lambda contractor_name, contact_email, repos, access_level, project: {
        "contractor_name": contractor_name,
        "contact_email": contact_email,
        "repos": repos,
        "access_level": access_level,
        "project": project,
    },
)
def grant_repo_access(contractor_name: str, contact_email: str,
                      repos: list, access_level: str, project: str) -> dict:
    """
    Grant contractor access to project repositories.
    Requires manager approval.
    """
    return {"access_granted": True, "contractor": contractor_name, "repos": repos}


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Contractor Onboarding Agent Demo")
    print("="*60)

    # Scenario 1: Send NDA -- auto-approved
    scenario("Scenario 1: Send NDA -- auto-approved")
    c = CONTRACTORS[0]
    nda = CONTRACT_TEMPLATES["standard_nda"]
    try:
        result = send_nda(
            c["name"], c["contact"], "standard_nda",
            nda["duration_months"], nda["scope"],
        )
        print(f"  NDA sent to {result['contractor']} ({result['type']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 2: Payment agreement -- Legal Counsel approval
    scenario("Scenario 2: Payment agreement -- Legal Counsel approval")
    c = CONTRACTORS[0]
    proj = PROJECTS[0]
    hours = proj["budget"] // c["rate_hourly"]
    try:
        result = send_payment_agreement(
            c["name"], c["contact"], proj["name"],
            c["rate_hourly"], hours, proj["budget"],
        )
        print(f"  Agreement sent to {result['contractor']}: ${result['budget']:,} budget")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 3: Large contract -- Legal Counsel + CEO (all_of_n)
    scenario("Scenario 3: Large contract ($120k) -- Legal + CEO required")
    c = CONTRACTORS[1]
    proj = PROJECTS[1]
    print("  Both Legal Counsel and CEO must approve.")
    try:
        result = execute_large_contract(
            c["name"], c["contact"], proj["name"],
            proj["budget"], proj["duration_months"],
            "Full ETL pipeline migration with documentation and runbooks",
        )
        print(f"  Contract executed: {result['contractor']}, ${result['value']:,}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 4: Repo access -- manager approval
    scenario("Scenario 4: Repo access -- manager approval required")
    c = CONTRACTORS[2]
    proj = PROJECTS[2]
    try:
        result = grant_repo_access(
            c["name"], c["contact"], proj["repos"],
            "read-only", proj["name"],
        )
        print(f"  Repo access granted to {result['contractor']}: {', '.join(result['repos'])}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

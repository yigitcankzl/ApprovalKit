"""
Demo Agent -- Access Provisioning
==================================
Simulates an AI agent that provisions and revokes system access
for employees. Every access change is gated behind ApprovalKit rules.

Rule configuration (set up via dashboard or setup_rules.py):

  github-prod : standard_access
    read-only repos        -> specific [it_admin]

  github-prod : admin_access
    admin / write repos    -> specific [cto]

  github-prod : financial_access
    billing & finance      -> all_of_n [cfo, cto]

  github-prod : revoke_departed
    departing employee     -> no rule  (auto-approved)

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/access-provisioning-agent/agent.py
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
    user_id="auth0|access_provisioning_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

EMPLOYEES = [
    {"name": "Alice Park", "email": "alice.park@company.com", "department": "Engineering", "role": "developer"},
    {"name": "Bob Martinez", "email": "bob.m@company.com", "department": "Engineering", "role": "tech_lead"},
    {"name": "Carol Nguyen", "email": "carol.n@company.com", "department": "Finance", "role": "analyst"},
    {"name": "Dave Ross", "email": "dave.ross@company.com", "department": "Engineering", "role": "developer", "departing": True},
]

REPO_GROUPS = {
    "standard": ["frontend-app", "docs", "design-system"],
    "admin": ["infrastructure", "ci-cd-pipelines", "secrets-manager"],
    "financial": ["billing-service", "revenue-dashboard", "payroll-integration"],
}

ACCESS_LEVELS = {
    "standard": "read",
    "admin": "admin",
    "financial": "read-write",
}

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="github-prod",
    action="standard_access",
    params_fn=lambda employee_name, employee_email, repos, access_level: {
        "employee_name": employee_name,
        "employee_email": employee_email,
        "repos": repos,
        "access_level": access_level,
    },
)
def grant_standard_access(employee_name: str, employee_email: str,
                          repos: list, access_level: str) -> dict:
    """
    Grant standard read-only repo access.
    Requires IT Admin approval.
    """
    return {"granted": True, "employee": employee_name, "repos": repos}


@kit.requires_approval(
    connection="github-prod",
    action="admin_access",
    params_fn=lambda employee_name, employee_email, repos, access_level: {
        "employee_name": employee_name,
        "employee_email": employee_email,
        "repos": repos,
        "access_level": access_level,
    },
)
def grant_admin_access(employee_name: str, employee_email: str,
                       repos: list, access_level: str) -> dict:
    """
    Grant admin-level repo access (infrastructure, CI/CD, secrets).
    Requires CTO approval -- elevated privilege.
    """
    return {"granted": True, "employee": employee_name, "repos": repos}


@kit.requires_approval(
    connection="github-prod",
    action="financial_access",
    params_fn=lambda employee_name, employee_email, repos, access_level, justification: {
        "employee_name": employee_name,
        "employee_email": employee_email,
        "repos": repos,
        "access_level": access_level,
        "justification": justification,
    },
)
def grant_financial_access(employee_name: str, employee_email: str,
                           repos: list, access_level: str, justification: str) -> dict:
    """
    Grant access to financial repositories.
    Requires both CFO and CTO approval (all_of_n).
    """
    return {"granted": True, "employee": employee_name, "repos": repos}


@kit.requires_approval(
    connection="github-prod",
    action="revoke_departed",
    params_fn=lambda employee_name, employee_email, repos_revoked, reason: {
        "employee_name": employee_name,
        "employee_email": employee_email,
        "repos_revoked": repos_revoked,
        "reason": reason,
    },
)
def revoke_departed_access(employee_name: str, employee_email: str,
                           repos_revoked: list, reason: str) -> dict:
    """
    Revoke all access for a departing employee.
    Auto-approved -- security-critical, immediate action required.
    """
    return {"revoked": True, "employee": employee_name, "repos_revoked": repos_revoked}


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Access Provisioning Agent Demo")
    print("="*60)

    # Scenario 1: Standard access -- IT Admin approval
    scenario("Scenario 1: Standard repo access -- IT Admin approval")
    emp = EMPLOYEES[0]
    repos = REPO_GROUPS["standard"]
    try:
        result = grant_standard_access(
            emp["name"], emp["email"], repos, ACCESS_LEVELS["standard"],
        )
        print(f"  Access granted to {result['employee']}: {', '.join(result['repos'])}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 2: Admin access -- CTO approval
    scenario("Scenario 2: Admin repo access -- CTO approval required")
    emp = EMPLOYEES[1]
    repos = REPO_GROUPS["admin"]
    try:
        result = grant_admin_access(
            emp["name"], emp["email"], repos, ACCESS_LEVELS["admin"],
        )
        print(f"  Admin access granted to {result['employee']}: {', '.join(result['repos'])}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 3: Financial access -- CFO + CTO (all_of_n)
    scenario("Scenario 3: Financial repo access -- CFO + CTO required")
    emp = EMPLOYEES[2]
    repos = REPO_GROUPS["financial"]
    print("  Both CFO and CTO must approve.")
    try:
        result = grant_financial_access(
            emp["name"], emp["email"], repos, ACCESS_LEVELS["financial"],
            "Quarterly audit requires direct repo access to billing data",
        )
        print(f"  Financial access granted to {result['employee']}: {', '.join(result['repos'])}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 4: Revoke departed employee -- auto-approved
    scenario("Scenario 4: Revoke departed employee -- auto-approved")
    emp = EMPLOYEES[3]
    all_repos = REPO_GROUPS["standard"] + REPO_GROUPS["admin"]
    try:
        result = revoke_departed_access(
            emp["name"], emp["email"], all_repos,
            "Employee last day 2026-03-27, offboarding triggered",
        )
        print(f"  Access revoked for {result['employee']}: {len(result['repos_revoked'])} repos")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

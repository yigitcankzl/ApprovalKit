"""
Demo Agent — Security Incident Response
========================================
Simulates an AI agent that handles security incidents: logging alerts,
locking repositories, revoking access tokens. Low-severity alerts are
auto-approved. Repo locks require the security lead. Token revocation
requires both the CTO and security lead (all_of_n).

Rule configuration:

  github-prod : lock_repo
    any                 -> specific [security_lead]

  github-prod : revoke_tokens
    any                 -> all_of_n [cto, security_lead]

  slack-prod : send_message
    channel=#security   -> specific [security_lead]
    channel=#incidents  -> any_one  [incident_commander]

  pagerduty-prod : create_incident
    severity=critical   -> specific [security_lead]
    severity=high       -> any_one  [security_engineer]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python examples/security-incident-agent/agent.py
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
    user_id="auth0|security_incident_agent",
    poll_interval=3,
    timeout=180,
)

# ── Simulated data ────────────────────────────────────────────────────────────

INCIDENTS = {
    "INC-4401": {
        "type": "credential_leak",
        "severity": "critical",
        "repo": "backend-api",
        "description": "AWS keys found in public commit",
    },
    "INC-4402": {
        "type": "brute_force",
        "severity": "high",
        "repo": "auth-service",
        "description": "Sustained brute-force attack on /login endpoint",
    },
    "INC-4403": {
        "type": "dependency_vuln",
        "severity": "medium",
        "repo": "frontend-app",
        "description": "CVE-2025-31337 in transitive dependency",
    },
}

# ── Action definitions ────────────────────────────────────────────────────────

@kit.requires_approval(
    connection="slack-prod",
    action="send_message",
    params_fn=lambda channel, message: {
        "channel": channel,
        "message": message,
    },
)
def log_alert(channel: str, message: str) -> dict:
    """Log a security alert to Slack. Low-severity alerts are auto-approved."""
    return {"channel": channel, "posted": True}


@kit.requires_approval(
    connection="github-prod",
    action="lock_repo",
    params_fn=lambda repo, reason, incident_id: {
        "repo": repo,
        "reason": reason,
        "incident_id": incident_id,
    },
)
def lock_repo(repo: str, reason: str, incident_id: str) -> dict:
    """Lock a GitHub repository to prevent further commits. Requires security_lead."""
    return {"repo": repo, "locked": True, "incident_id": incident_id}


@kit.requires_approval(
    connection="github-prod",
    action="revoke_tokens",
    params_fn=lambda repo, token_type, incident_id: {
        "repo": repo,
        "token_type": token_type,
        "incident_id": incident_id,
    },
)
def revoke_access(repo: str, token_type: str, incident_id: str) -> dict:
    """Revoke access tokens. Requires CTO + security_lead (all_of_n)."""
    return {"repo": repo, "token_type": token_type, "revoked": True}


@kit.requires_approval(
    connection="pagerduty-prod",
    action="create_incident",
    params_fn=lambda severity, title, description: {
        "severity": severity,
        "title": title,
        "description": description,
    },
)
def create_incident(severity: str, title: str, description: str) -> dict:
    """Create a PagerDuty incident to mobilize the response team."""
    return {"created": True, "severity": severity, "title": title}


# ── Scenarios ─────────────────────────────────────────────────────────────────

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Security Incident Agent Demo")
    print("="*60)

    inc = INCIDENTS["INC-4403"]

    # ── Scenario 1: Log low-severity alert — auto-approved ────────────
    scenario("Scenario 1: Log medium-severity alert — auto-approved")
    try:
        result = log_alert(
            "#security",
            f"[{inc['severity'].upper()}] {inc['description']} in {inc['repo']}",
        )
        print(f"  Alert posted to {result['channel']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    inc = INCIDENTS["INC-4401"]

    # ── Scenario 2: Lock repo — security_lead approval ────────────────
    scenario("Scenario 2: Lock repo (credential leak) — security_lead required")
    try:
        result = lock_repo(
            inc["repo"],
            inc["description"],
            "INC-4401",
        )
        print(f"  Repo {result['repo']} locked (incident: {result['incident_id']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 3: Revoke tokens — CTO + security_lead ──────────────
    scenario("Scenario 3: Revoke AWS tokens — CTO + security_lead (all_of_n)")
    print("  Both CTO and security_lead must approve this action.")
    try:
        result = revoke_access(
            inc["repo"],
            "aws_access_keys",
            "INC-4401",
        )
        print(f"  Tokens revoked: {result['token_type']} for {result['repo']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 4: Create PagerDuty incident — critical ──────────────
    scenario("Scenario 4: PagerDuty critical incident — security_lead approval")
    try:
        result = create_incident(
            "critical",
            f"[INC-4401] {inc['type'].replace('_', ' ').title()}",
            inc["description"],
        )
        print(f"  Incident created: {result['title']} (severity={result['severity']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    inc = INCIDENTS["INC-4402"]

    # ── Scenario 5: Brute-force — log + escalate ─────────────────────
    scenario("Scenario 5: Brute-force alert — log and page team")
    try:
        result = log_alert(
            "#incidents",
            f"[{inc['severity'].upper()}] {inc['description']}",
        )
        print(f"  Alert posted to {result['channel']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

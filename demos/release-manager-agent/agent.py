"""
Demo Agent — Release Manager
=============================
Simulates an AI release manager that coordinates deployments across
environments. Staging deploys are auto-approved. Production requires
a maintainer. Hotfixes require on-call approval. Rollbacks have a
tight 2-minute timeout.

Rule configuration:

  github-main : deploy
    environment=staging     -> no rule (auto-approved)
    environment=production  -> any_one [maintainer]
    environment=hotfix      -> specific [oncall_engineer]

  github-main : rollback
    any                     -> specific [release_lead] + 2min timeout

  slack-prod : send_message
    channel=#releases       -> any_one [team_lead]
    channel=#incidents      -> specific [oncall_engineer]

  pagerduty-prod : notify_oncall
    severity=p1             -> specific [oncall_engineer]
    severity=p2             -> any_one [team_lead]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/release-manager-agent/agent.py
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
    user_id="auth0|release_manager_agent",
    poll_interval=3,
    timeout=180,
)

# ── Simulated data ────────────────────────────────────────────────────────────

VERSIONS = {
    "api-gateway": {"current": "v3.12.0", "previous": "v3.11.4", "candidate": "v3.13.0-rc1"},
    "auth-service": {"current": "v2.8.1", "previous": "v2.7.9", "candidate": "v2.9.0-rc2"},
    "payments": {"current": "v5.1.0", "previous": "v5.0.3", "candidate": "v5.2.0-rc1"},
}

ENVIRONMENTS = ["staging", "production"]

SERVICES = list(VERSIONS.keys())

# ── Action definitions ────────────────────────────────────────────────────────

@kit.requires_approval(
    connection="github-main",
    action="deploy",
    params_fn=lambda ref, environment, service: {
        "ref": ref,
        "environment": environment,
        "service": service,
    },
)
def deploy(ref: str, environment: str, service: str) -> dict:
    """Deploy a service version to an environment via GitHub Actions."""
    return {"deployed": ref, "environment": environment, "service": service}


@kit.requires_approval(
    connection="github-main",
    action="rollback",
    params_fn=lambda environment, service, target_version, reason: {
        "environment": environment,
        "service": service,
        "target_version": target_version,
        "reason": reason,
    },
)
def rollback(environment: str, service: str, target_version: str, reason: str) -> dict:
    """Roll back a service to a previous version. 2-minute approval timeout."""
    return {"rolled_back_to": target_version, "service": service, "environment": environment}


@kit.requires_approval(
    connection="slack-prod",
    action="send_message",
    params_fn=lambda channel, message: {
        "channel": channel,
        "message": message,
    },
)
def notify_slack(channel: str, message: str) -> dict:
    """Post a deployment notification to Slack."""
    return {"channel": channel, "posted": True}


@kit.requires_approval(
    connection="pagerduty-prod",
    action="notify_oncall",
    params_fn=lambda severity, title, service: {
        "severity": severity,
        "title": title,
        "service": service,
    },
)
def page_oncall(severity: str, title: str, service: str) -> dict:
    """Page the on-call engineer via PagerDuty."""
    return {"paged": True, "severity": severity, "service": service}


# ── Scenarios ─────────────────────────────────────────────────────────────────

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Release Manager Agent Demo")
    print("="*60)

    # ── Scenario 1: Deploy to staging — auto-approved ─────────────────
    scenario("Scenario 1: Deploy api-gateway to staging — auto-approved")
    try:
        result = deploy(
            VERSIONS["api-gateway"]["candidate"],
            "staging",
            "api-gateway",
        )
        print(f"  Deployed {result['deployed']} to {result['environment']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 2: Deploy to production — maintainer approval ────────
    scenario("Scenario 2: Deploy payments to production — maintainer required")
    try:
        result = deploy(
            VERSIONS["payments"]["candidate"],
            "production",
            "payments",
        )
        print(f"  Deployed {result['deployed']} to {result['environment']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 3: Hotfix deploy — on-call approval ──────────────────
    scenario("Scenario 3: Hotfix auth-service — on-call engineer required")
    try:
        result = deploy(
            "hotfix-auth-bypass-2024",
            "production",
            "auth-service",
        )
        print(f"  Hotfix deployed: {result['deployed']} to {result['environment']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 4: Rollback — 2-minute timeout ──────────────────────
    scenario("Scenario 4: Rollback payments — 2min timeout, release_lead only")
    try:
        result = rollback(
            "production",
            "payments",
            VERSIONS["payments"]["previous"],
            "P0: payment processing latency spike after v5.2.0-rc1",
        )
        print(f"  Rolled back {result['service']} to {result['rolled_back_to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 5: Slack notification to #releases ───────────────────
    scenario("Scenario 5: Notify #releases channel")
    try:
        result = notify_slack(
            "#releases",
            "api-gateway v3.13.0-rc1 deployed to staging. Smoke tests passing.",
        )
        print(f"  Posted to {result['channel']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 6: Page on-call for P1 ───────────────────────────────
    scenario("Scenario 6: PagerDuty P1 — on-call engineer approval")
    try:
        result = page_oncall(
            "p1",
            "auth-service unresponsive after hotfix deploy",
            "auth-service",
        )
        print(f"  Paged on-call: severity={result['severity']}, service={result['service']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

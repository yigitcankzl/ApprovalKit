"""
Demo Agent — DevOps
===================
Simulates a CI/CD agent that deploys to GitHub-managed environments.
Staging is auto-approved. Production requires a maintainer.
Rollbacks require the lead. Deployments after 23:00 are blocked.

Rules:
  github-main : deploy
    environment=staging    → no rule (auto)
    environment=production → any_one [maintainer]
    after 23:00            → blackout window

  github-main : rollback
    environment=production → specific [lead]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/devops_agent.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk"))
from approvalkit import ApprovalKit, ApprovalDenied

kit = ApprovalKit(
    base_url=os.environ.get("APPROVALKIT_URL", "http://localhost:8000"),
    api_key=os.environ.get("APPROVALKIT_API_KEY", ""),
    hmac_secret=os.environ.get("APPROVALKIT_HMAC_SECRET", ""),
    user_id="auth0|devops_agent",
    poll_interval=3,
    timeout=180,
)

# ── Actions ───────────────────────────────────────────────────────────────────

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
    """Deploy a ref to an environment via GitHub Actions."""
    return {"deployed": ref, "environment": environment, "service": service}


@kit.requires_approval(
    connection="github-main",
    action="rollback",
    params_fn=lambda env, version, reason: {
        "env": env,
        "version": version,
        "reason": reason,
    },
)
def rollback(env: str, version: str, reason: str) -> dict:
    """Roll back a production deployment to a previous version."""
    return {"rolled_back_to": version, "env": env}


# ── Scenarios ─────────────────────────────────────────────────────────────────

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  DevOps Agent Demo")
    print("="*60)

    scenario("Scenario 1: Deploy to staging — no rule, auto-approved")
    try:
        result = deploy("main", "staging", "api")
        print(f"  Deployed {result['deployed']} to {result['environment']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    scenario("Scenario 2: Deploy to production — maintainer approval required")
    try:
        result = deploy("v2.4.1", "production", "api")
        print(f"  Deployed {result['deployed']} to {result['environment']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    scenario("Scenario 3: Rollback production — lead only (specific)")
    try:
        result = rollback("production", "v2.3.8", "p0 latency spike on v2.4.1")
        print(f"  Rolled back to {result['rolled_back_to']} on {result['env']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

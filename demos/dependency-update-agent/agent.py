"""
Demo Agent — Dependency Update
==============================
Simulates an AI agent that manages dependency updates. Patch updates
are auto-approved. Minor version updates require a lead engineer.
Major version updates require approval from the entire team (all_of_n).

Rule configuration:

  github-prod : merge_pr
    update_type=patch   -> no rule (auto-approved)
    update_type=minor   -> specific [lead_engineer]
    update_type=major   -> all_of_n [lead_engineer, frontend_lead, backend_lead]

  slack-prod : send_message
    channel=#deps       -> any_one [team_lead]
    channel=#engineering -> specific [engineering_manager]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/dependency-update-agent/agent.py
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
    user_id="auth0|dependency_update_agent",
    poll_interval=3,
    timeout=180,
)

# ── Simulated data ────────────────────────────────────────────────────────────

PACKAGES = {
    "lodash": {
        "current": "4.17.21",
        "available_patch": "4.17.22",
        "available_minor": "4.18.0",
        "available_major": "5.0.0",
        "repo": "frontend-app",
    },
    "react": {
        "current": "18.2.0",
        "available_patch": "18.2.1",
        "available_minor": "18.3.0",
        "available_major": "19.0.0",
        "repo": "frontend-app",
    },
    "webpack": {
        "current": "5.88.2",
        "available_patch": "5.88.3",
        "available_minor": "5.89.0",
        "available_major": "6.0.0",
        "repo": "frontend-app",
    },
}

# ── Action definitions ────────────────────────────────────────────────────────

@kit.requires_approval(
    connection="github-prod",
    action="merge_pr",
    params_fn=lambda package, from_version, to_version, update_type, repo: {
        "package": package,
        "from_version": from_version,
        "to_version": to_version,
        "update_type": update_type,
        "repo": repo,
    },
)
def merge_update_pr(package: str, from_version: str, to_version: str, update_type: str, repo: str) -> dict:
    """Merge a dependency update PR. Approval level scales with update type."""
    return {
        "package": package,
        "from": from_version,
        "to": to_version,
        "update_type": update_type,
        "merged": True,
    }


@kit.requires_approval(
    connection="slack-prod",
    action="send_message",
    params_fn=lambda channel, message: {
        "channel": channel,
        "message": message,
    },
)
def notify_slack(channel: str, message: str) -> dict:
    """Post a dependency update notification to Slack."""
    return {"channel": channel, "posted": True}


# ── Scenarios ─────────────────────────────────────────────────────────────────

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Dependency Update Agent Demo")
    print("="*60)

    # ── Scenario 1: Patch update — auto-approved ──────────────────────
    pkg = PACKAGES["lodash"]
    scenario("Scenario 1: lodash patch update — auto-approved")
    try:
        result = merge_update_pr(
            "lodash",
            pkg["current"],
            pkg["available_patch"],
            "patch",
            pkg["repo"],
        )
        print(f"  Merged: {result['package']} {result['from']} -> {result['to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 2: Minor update — lead_engineer approval ─────────────
    pkg = PACKAGES["react"]
    scenario("Scenario 2: react minor update — lead_engineer required")
    try:
        result = merge_update_pr(
            "react",
            pkg["current"],
            pkg["available_minor"],
            "minor",
            pkg["repo"],
        )
        print(f"  Merged: {result['package']} {result['from']} -> {result['to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 3: Major update — entire team (all_of_n) ────────────
    pkg = PACKAGES["webpack"]
    scenario("Scenario 3: webpack major update — all team leads (all_of_n)")
    print("  lead_engineer, frontend_lead, and backend_lead must all approve.")
    try:
        result = merge_update_pr(
            "webpack",
            pkg["current"],
            pkg["available_major"],
            "major",
            pkg["repo"],
        )
        print(f"  Merged: {result['package']} {result['from']} -> {result['to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 4: react major update — all team leads ──────────────
    pkg = PACKAGES["react"]
    scenario("Scenario 4: react major update (18 -> 19) — all team leads")
    print("  Breaking change: concurrent mode is now default.")
    try:
        result = merge_update_pr(
            "react",
            pkg["current"],
            pkg["available_major"],
            "major",
            pkg["repo"],
        )
        print(f"  Merged: {result['package']} {result['from']} -> {result['to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 5: Notify #engineering about all updates ────────────
    scenario("Scenario 5: Summary to #engineering — manager approval")
    try:
        result = notify_slack(
            "#engineering",
            "Dependency sweep complete: 2 patch (auto-merged), 1 minor (pending), 2 major (pending team review).",
        )
        print(f"  Posted to {result['channel']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

"""
Demo Agent — Open Source Project
==================================
Simulates a bot that manages an open source project on GitHub.
Small PRs auto-merge. Large PRs go through k-of-n voting.
npm publishes and treasury spending require multi-maintainer sign-off.

Rules:
  github-main : merge_pr
    lines_changed < 100  → no rule (auto)
    lines_changed >= 100 → k_of_n (k=2) [maintainers]

  npm-registry : publish
    version=patch        → specific [lead_maintainer]
    version=major        → k_of_n (k=2/3) [maintainers]

  stripe-prod : payout
    amount <= 100        → specific [treasurer]
    amount > 100         → all_of_n [treasurer, lead_maintainer]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/opensource_agent.py
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
    user_id="auth0|opensource_bot",
    poll_interval=3,
    timeout=180,
)

# ── Actions ───────────────────────────────────────────────────────────────────

@kit.requires_approval(
    connection="github-main",
    action="merge_pr",
    params_fn=lambda pr_number, title, lines_changed, author: {
        "pr_number": pr_number,
        "title": title,
        "lines_changed": lines_changed,
        "author": author,
    },
)
def merge_pr(pr_number: int, title: str, lines_changed: int, author: str) -> dict:
    """Merge a pull request. Large PRs require k-of-n maintainer vote."""
    return {"merged": pr_number, "title": title}


@kit.requires_approval(
    connection="npm-registry",
    action="publish",
    params_fn=lambda package, version, version_type: {
        "package": package,
        "version": version,
        "version_type": version_type,
    },
)
def publish_npm(package: str, version: str, version_type: str) -> dict:
    """Publish a new npm version. Major versions require a quorum vote."""
    return {"published": package, "version": version}


@kit.requires_approval(
    connection="stripe-prod",
    action="payout",
    params_fn=lambda amount, recipient, purpose: {
        "amount_usd": amount,
        "recipient": recipient,
        "purpose": purpose,
    },
)
def treasury_payout(amount: int, recipient: str, purpose: str) -> dict:
    """Disburse funds from the project treasury."""
    return {"paid": amount, "to": recipient}


# ── Scenarios ─────────────────────────────────────────────────────────────────

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Open Source Project Bot Demo")
    print("="*60)

    scenario("Scenario 1: Small PR (42 lines) — auto-merged")
    try:
        result = merge_pr(1847, "fix: correct typo in README", 42, "contributor")
        print(f"  Merged PR #{result['merged']}: {result['title']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    scenario("Scenario 2: Large PR (380 lines) — k-of-n vote (2/3 maintainers)")
    print("  At least 2 maintainers must approve.")
    try:
        result = merge_pr(1901, "feat: rewrite core parser for v3", 380, "core-contributor")
        print(f"  Merged PR #{result['merged']}: {result['title']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    scenario("Scenario 3: npm patch publish — lead maintainer only")
    try:
        result = publish_npm("approvalkit-sdk", "1.2.4", "patch")
        print(f"  Published {result['published']}@{result['version']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    scenario("Scenario 4: npm major publish — k-of-n maintainer vote")
    print("  Breaking change: 2/3 maintainers must approve.")
    try:
        result = publish_npm("approvalkit-sdk", "2.0.0", "major")
        print(f"  Published {result['published']}@{result['version']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    scenario("Scenario 5: Treasury payout $80 — treasurer approval")
    try:
        result = treasury_payout(80, "contributor@example.com", "Bounty for issue #312")
        print(f"  Paid ${result['paid']} to {result['to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    scenario("Scenario 6: Treasury payout $500 — treasurer + lead maintainer")
    print("  Large disbursement: both must approve.")
    try:
        result = treasury_payout(500, "infra@example.com", "Annual hosting costs")
        print(f"  Paid ${result['paid']} to {result['to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

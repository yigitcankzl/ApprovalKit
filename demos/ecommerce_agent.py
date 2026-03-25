"""
Demo Agent 1 — E-Commerce
=========================
Simulates an AI shopping agent that handles payments, refunds,
and team notifications. Every high-risk action is gated behind
an ApprovalKit rule.

Rule configuration (set up via dashboard or setup_rules.py):

  stripe-prod : charge
    amount < 100      → no rule  (auto-approved)
    amount 100-999    → any_one  [sales_manager]
    amount >= 1000    → all_of_n [sales_manager, cfo]  (step-up)

  stripe-prod : refund
    amount < 50       → any_one  [cs_agent]
    amount >= 50      → specific [cs_manager]  + partial_approval

  slack-prod : send_message
    channel=#general  → any_one  [team_lead]
    channel=#finance  → specific [cfo]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/ecommerce_agent.py
"""

import os
import sys
import time

# Add sdk to path if not installed via pip
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk"))

from approvalkit import ApprovalKit, ApprovalDenied

kit = ApprovalKit(
    base_url=os.environ.get("APPROVALKIT_URL", "http://localhost:8000"),
    api_key=os.environ.get("APPROVALKIT_API_KEY", ""),
    hmac_secret=os.environ.get("APPROVALKIT_HMAC_SECRET", ""),
    user_id="auth0|ecommerce_agent",
    poll_interval=3,
    timeout=180,
)

# ── Action definitions ────────────────────────────────────────────────────────

@kit.requires_approval(
    connection="stripe-prod",
    action="charge",
    params_fn=lambda amount, customer, description: {
        "amount_usd": amount,
        "customer": customer,
        "description": description,
    },
)
def charge_customer(amount: int, customer: str, description: str) -> dict:
    """
    Charge a customer via Stripe.
    Token Vault executes the actual API call after approval.
    The agent never sees the Stripe secret key.
    """
    return {"charged": amount, "customer": customer}


@kit.requires_approval(
    connection="stripe-prod",
    action="refund",
    params_fn=lambda amount, customer, reason: {
        "amount_usd": amount,
        "customer": customer,
        "reason": reason,
    },
)
def refund_customer(amount: int, customer: str, reason: str) -> dict:
    """
    Issue a refund. CS Manager may modify the amount before approving
    (partial approval) — the agent reads back the final amount from
    the job status.
    """
    return {"refunded": amount, "customer": customer}


@kit.requires_approval(
    connection="slack-prod",
    action="send_message",
    params_fn=lambda channel, message: {
        "channel": channel,
        "message": message,
    },
)
def notify_slack(channel: str, message: str) -> dict:
    """Post a message to Slack after approval."""
    return {"channel": channel, "posted": True}


# ── Scenarios ─────────────────────────────────────────────────────────────────

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  E-Commerce Agent Demo")
    print("="*60)

    # ── Scenario 1: Small order — no rule, auto-approved ──────────────
    scenario("Scenario 1: Small order ($49) — no rule, auto-approved")
    try:
        result = charge_customer(49, "alice@example.com", "T-shirt")
        print(f"  Charge complete: ${result['charged']} to {result['customer']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 2: Medium order — sales_manager approves ─────────────
    scenario("Scenario 2: Medium order ($349) — waiting for sales_manager")
    try:
        result = charge_customer(349, "bob@example.com", "Premium annual plan")
        print(f"  Charge complete: ${result['charged']} to {result['customer']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 3: Large order — step-up (sales_manager + CFO) ───────
    scenario("Scenario 3: Large order ($5,000) — STEP-UP (all_of_n)")
    print("  Both sales_manager and CFO must approve.")
    try:
        result = charge_customer(5000, "corp@example.com", "Enterprise license")
        print(f"  Charge complete: ${result['charged']} to {result['customer']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 4: Refund — partial approval (CS Manager may edit amount) ──
    scenario("Scenario 4: Refund ($340) — CS Manager may modify amount")
    try:
        result = refund_customer(340, "alice@example.com", "Wrong size")
        print(f"  Refund complete: ${result['refunded']} to {result['customer']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 5: Slack to #finance — CFO must approve ──────────────
    scenario("Scenario 5: Slack → #finance — CFO approval required")
    try:
        result = notify_slack("#finance", "Monthly revenue: $54,320 — all targets met")
        print(f"  Posted to {result['channel']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

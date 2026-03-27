"""
Demo Agent — Subscription Manager
===================================
Simulates an AI subscription management agent that handles plan
upgrades, enterprise pricing, and bulk cancellations.

Rule configuration (set up via dashboard or setup_rules.py):

  stripe-prod : subscription
    free -> paid (Pro/Business) -> no rule  (auto-approved)
    enterprise pricing          -> specific [ceo]
    bulk cancel                 -> specific [cfo]

  slack-prod : send_message
    subscription changes        -> any_one  [team_lead]

  gmail-prod : send_email
    plan change confirmations   -> no rule  (auto-approved)

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/subscription-agent/agent.py
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
    user_id="auth0|subscription_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

PLANS = {
    "free": {"name": "Free", "price": 0, "seats": 5, "features": ["basic_analytics"]},
    "pro": {"name": "Pro", "price": 29, "seats": 25, "features": ["analytics", "api_access", "priority_support"]},
    "business": {"name": "Business", "price": 99, "seats": 100, "features": ["analytics", "api_access", "sso", "dedicated_support"]},
    "enterprise": {"name": "Enterprise", "price": None, "seats": None, "features": ["everything", "custom_sla", "on_prem"]},
}

SUBSCRIBERS = [
    {"org": "TinyStartup", "email": "admin@tinystartup.io", "plan": "free", "seats_used": 3},
    {"org": "GrowthCo", "email": "ops@growthco.com", "plan": "pro", "seats_used": 22},
    {"org": "ScaleUp Ltd", "email": "it@scaleup.co", "plan": "business", "seats_used": 87},
    {"org": "MegaCorp", "email": "procurement@megacorp.com", "plan": "business", "seats_used": 95},
    {"org": "FailingCo", "email": "admin@failingco.com", "plan": "pro", "seats_used": 4},
]

BULK_CANCEL_LIST = [
    {"org": "InactiveCo", "email": "info@inactiveco.com", "plan": "pro", "last_login_days": 180},
    {"org": "GhostOrg", "email": "ghost@ghostorg.io", "plan": "pro", "last_login_days": 210},
    {"org": "DormantLLC", "email": "hello@dormant.co", "plan": "business", "last_login_days": 150},
]

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="stripe-prod",
    action="subscription",
    params_fn=lambda org, email, from_plan, to_plan, monthly_price: {
        "organization": org,
        "customer_email": email,
        "from_plan": from_plan,
        "to_plan": to_plan,
        "monthly_price_usd": monthly_price,
    },
)
def upgrade_plan(org: str, email: str, from_plan: str, to_plan: str, monthly_price: int) -> dict:
    """
    Upgrade a subscriber's plan.
    Auto-approved for free->paid transitions.
    Token Vault updates the Stripe subscription after approval.
    """
    return {"org": org, "new_plan": to_plan, "price": monthly_price}


@kit.requires_approval(
    connection="stripe-prod",
    action="subscription",
    params_fn=lambda org, email, seats, custom_price, contract_months, features: {
        "organization": org,
        "customer_email": email,
        "seats": seats,
        "custom_monthly_price_usd": custom_price,
        "contract_months": contract_months,
        "custom_features": features,
        "enterprise_deal": True,
    },
)
def enterprise_pricing(org: str, email: str, seats: int, custom_price: int, contract_months: int, features: list) -> dict:
    """
    Create a custom enterprise pricing deal.
    Requires CEO approval due to custom contract terms.
    """
    return {"org": org, "seats": seats, "annual_value": custom_price * contract_months}


@kit.requires_approval(
    connection="stripe-prod",
    action="subscription",
    params_fn=lambda orgs, reason, total_mrr_impact: {
        "organizations": orgs,
        "reason": reason,
        "total_mrr_impact_usd": total_mrr_impact,
        "bulk_operation": True,
        "count": len(orgs),
    },
)
def bulk_cancel(orgs: list, reason: str, total_mrr_impact: int) -> dict:
    """
    Bulk cancel inactive subscriptions.
    Requires CFO approval due to revenue impact.
    """
    return {"cancelled": len(orgs), "mrr_impact": total_mrr_impact}


@kit.requires_approval(
    connection="slack-prod",
    action="send_message",
    params_fn=lambda channel, message: {
        "channel": channel,
        "message": message,
    },
)
def notify_slack(channel: str, message: str) -> dict:
    """Post a subscription change notification to Slack."""
    return {"channel": channel, "posted": True}


@kit.requires_approval(
    connection="gmail-prod",
    action="send_email",
    params_fn=lambda recipient, subject, body: {
        "to": recipient,
        "subject": subject,
        "body": body,
    },
)
def send_plan_confirmation(recipient: str, subject: str, body: str) -> dict:
    """Send a plan change confirmation email."""
    return {"sent_to": recipient}


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Subscription Manager Demo")
    print("="*60)

    # Scenario 1: Free -> Pro upgrade — auto-approved
    scenario("Scenario 1: Free -> Pro upgrade ($29/mo) — auto-approved")
    sub = SUBSCRIBERS[0]
    to_plan = PLANS["pro"]
    try:
        result = upgrade_plan(
            sub["org"], sub["email"], sub["plan"], "pro", to_plan["price"]
        )
        print(f"  {sub['org']} upgraded to {to_plan['name']} at ${to_plan['price']}/mo")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 2: Pro -> Business upgrade — auto-approved
    scenario("Scenario 2: Pro -> Business upgrade ($99/mo) — auto-approved")
    sub = SUBSCRIBERS[1]
    to_plan = PLANS["business"]
    try:
        result = upgrade_plan(
            sub["org"], sub["email"], sub["plan"], "business", to_plan["price"]
        )
        print(f"  {sub['org']} upgraded to {to_plan['name']} at ${to_plan['price']}/mo")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 3: Enterprise pricing — CEO approval required
    scenario("Scenario 3: Enterprise deal (500 seats, custom) — CEO required")
    sub = SUBSCRIBERS[3]
    print(f"  Custom deal for {sub['org']} — CEO must approve.")
    try:
        result = enterprise_pricing(
            sub["org"], sub["email"],
            seats=500,
            custom_price=8500,
            contract_months=24,
            features=["everything", "custom_sla", "on_prem", "dedicated_tam"],
        )
        fp = result["final_params"]
        annual = fp["custom_monthly_price_usd"] * fp["contract_months"]
        print(f"  Enterprise deal approved: {fp['organization']}")
        print(f"  {fp['seats']} seats, ${fp['custom_monthly_price_usd']}/mo, {fp['contract_months']}mo contract")
        print(f"  Total contract value: ${annual}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 4: Bulk cancel inactive accounts — CFO approval required
    scenario("Scenario 4: Bulk cancel 3 inactive orgs — CFO required")
    org_names = [o["org"] for o in BULK_CANCEL_LIST]
    total_mrr = sum(PLANS[o["plan"]]["price"] for o in BULK_CANCEL_LIST)
    print(f"  Orgs: {', '.join(org_names)}")
    print(f"  Total MRR impact: ${total_mrr}")
    try:
        result = bulk_cancel(org_names, "Inactive for 150+ days", total_mrr)
        fp = result["final_params"]
        print(f"  Cancelled {fp['count']} subscriptions (MRR impact: ${fp['total_mrr_impact_usd']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 5: Slack notification for upgrade
    scenario("Scenario 5: Slack notification — team_lead approval")
    try:
        result = notify_slack(
            "#subscriptions",
            "MegaCorp signed Enterprise deal: 500 seats, $8,500/mo, 24mo contract ($204,000 TCV)"
        )
        print(f"  Posted to {result['final_params']['channel']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 6: Confirmation email — auto-approved
    scenario("Scenario 6: Plan confirmation email — auto-approved")
    try:
        result = send_plan_confirmation(
            "admin@tinystartup.io",
            "Welcome to Pro!",
            "Hi TinyStartup,\n\nYour upgrade to the Pro plan ($29/mo) is now active. "
            "You now have access to analytics, API access, and priority support.\n\n"
            "Happy building!"
        )
        print(f"  Confirmation sent to {result['final_params']['to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

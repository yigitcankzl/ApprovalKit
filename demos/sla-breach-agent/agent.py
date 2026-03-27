"""
Demo Agent -- SLA Breach Response
===================================
Simulates an AI agent that handles SLA breach incidents: sending
notifications, issuing service credits, and processing large
compensation packages. Each tier is gated via ApprovalKit.

Rule configuration (set up via dashboard or setup_rules.py):

  slack-prod : notification
    any SLA breach         -> no rule  (auto-approved)

  stripe-prod : credit
    credit < $5000         -> specific [cs_manager]

  stripe-prod : compensation
    compensation >= $5000  -> all_of_n [cfo, legal_counsel]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/sla-breach-agent/agent.py
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
    user_id="auth0|sla_breach_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

SLA_TIERS = {
    "standard": {"uptime": "99.5%", "response_time_hrs": 24, "penalty_pct": 5},
    "premium": {"uptime": "99.9%", "response_time_hrs": 4, "penalty_pct": 10},
    "enterprise": {"uptime": "99.99%", "response_time_hrs": 1, "penalty_pct": 20},
}

INCIDENTS = [
    {
        "id": "INC-4401", "customer": "SmallBiz Co", "email": "ops@smallbiz.co",
        "tier": "standard", "downtime_hrs": 2.5, "monthly_spend": 500,
        "breach_type": "uptime",
    },
    {
        "id": "INC-4405", "customer": "MidMarket Inc", "email": "it@midmarket.com",
        "tier": "premium", "downtime_hrs": 1.2, "monthly_spend": 8000,
        "breach_type": "uptime",
    },
    {
        "id": "INC-4410", "customer": "Enterprise Global", "email": "sre@enterprise-global.com",
        "tier": "enterprise", "downtime_hrs": 0.5, "monthly_spend": 85000,
        "breach_type": "uptime",
    },
]

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="slack-prod",
    action="notification",
    params_fn=lambda incident_id, customer, breach_type, downtime_hrs, sla_tier: {
        "incident_id": incident_id,
        "customer": customer,
        "breach_type": breach_type,
        "downtime_hours": downtime_hrs,
        "sla_tier": sla_tier,
        "channel": "#sla-breaches",
    },
)
def send_breach_notification(incident_id: str, customer: str,
                             breach_type: str, downtime_hrs: float,
                             sla_tier: str) -> dict:
    """
    Send SLA breach notification to Slack.
    Auto-approved -- immediate visibility needed.
    """
    return {"notified": True, "incident": incident_id, "customer": customer}


@kit.requires_approval(
    connection="stripe-prod",
    action="credit",
    params_fn=lambda incident_id, customer, customer_email, credit_amount, monthly_spend, sla_tier: {
        "incident_id": incident_id,
        "customer": customer,
        "customer_email": customer_email,
        "credit_amount_usd": credit_amount,
        "monthly_spend_usd": monthly_spend,
        "sla_tier": sla_tier,
    },
)
def issue_service_credit(incident_id: str, customer: str,
                         customer_email: str, credit_amount: int,
                         monthly_spend: int, sla_tier: str) -> dict:
    """
    Issue service credit for SLA breach.
    Requires CS Manager approval.
    """
    return {"credited": True, "incident": incident_id, "amount": credit_amount}


@kit.requires_approval(
    connection="stripe-prod",
    action="compensation",
    params_fn=lambda incident_id, customer, customer_email, compensation_amount, monthly_spend, sla_tier, breakdown: {
        "incident_id": incident_id,
        "customer": customer,
        "customer_email": customer_email,
        "compensation_amount_usd": compensation_amount,
        "monthly_spend_usd": monthly_spend,
        "sla_tier": sla_tier,
        "compensation_breakdown": breakdown,
    },
)
def issue_compensation(incident_id: str, customer: str,
                       customer_email: str, compensation_amount: int,
                       monthly_spend: int, sla_tier: str,
                       breakdown: str) -> dict:
    """
    Issue large compensation for severe SLA breach.
    Requires both CFO and Legal Counsel approval (all_of_n).
    """
    return {"compensated": True, "incident": incident_id, "amount": compensation_amount}


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  SLA Breach Response Agent Demo")
    print("="*60)

    # Scenario 1: Breach notification -- auto-approved
    scenario("Scenario 1: Breach notification to Slack -- auto-approved")
    inc = INCIDENTS[0]
    try:
        result = send_breach_notification(
            inc["id"], inc["customer"], inc["breach_type"],
            inc["downtime_hrs"], inc["tier"],
        )
        print(f"  Notification sent for {result['incident']} ({result['customer']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 2: Service credit -- CS Manager approval
    scenario("Scenario 2: Service credit ($800) -- CS Manager required")
    inc = INCIDENTS[1]
    penalty_pct = SLA_TIERS[inc["tier"]]["penalty_pct"]
    credit = int(inc["monthly_spend"] * penalty_pct / 100)
    try:
        result = issue_service_credit(
            inc["id"], inc["customer"], inc["email"],
            credit, inc["monthly_spend"], inc["tier"],
        )
        print(f"  Credit issued for {result['incident']}: ${result['amount']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 3: Large compensation -- CFO + Legal (all_of_n)
    scenario("Scenario 3: Large compensation ($17,000) -- CFO + Legal required")
    inc = INCIDENTS[2]
    penalty_pct = SLA_TIERS[inc["tier"]]["penalty_pct"]
    compensation = int(inc["monthly_spend"] * penalty_pct / 100)
    print("  Both CFO and Legal Counsel must approve.")
    try:
        result = issue_compensation(
            inc["id"], inc["customer"], inc["email"],
            compensation, inc["monthly_spend"], inc["tier"],
            f"{penalty_pct}% of ${inc['monthly_spend']:,} monthly spend per enterprise SLA",
        )
        print(f"  Compensation issued for {result['incident']}: ${result['amount']:,}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

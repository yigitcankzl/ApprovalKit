"""
Demo Agent -- Support Escalation
==================================
Simulates an AI customer service agent that handles complaints at
different severity levels. Standard complaints auto-resolve; VIP
complaints need CS Manager approval; large compensations require
CFO and Legal sign-off.

Rule configuration (set up via dashboard or setup_rules.py):

  salesforce-prod : standard_complaint
    standard customer      -> no rule  (auto-approved)

  salesforce-prod : vip_complaint
    VIP customer           -> specific [cs_manager]

  stripe-prod : large_compensation
    compensation >= $5000  -> all_of_n [cfo, legal_counsel]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/support-escalation-agent/agent.py
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
    user_id="auth0|support_escalation_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

CUSTOMERS = [
    {"name": "Jane Doe", "email": "jane.doe@gmail.com", "tier": "standard", "account_id": "CUST-1001"},
    {"name": "GlobalTech Inc", "email": "support@globaltech.com", "tier": "vip", "account_id": "CUST-0042"},
    {"name": "MegaCorp Ltd", "email": "procurement@megacorp.com", "tier": "enterprise", "account_id": "CUST-0003"},
]

TICKETS = [
    {"id": "TKT-8812", "customer": CUSTOMERS[0], "issue": "Shipping delay on order #ORD-5543", "severity": "low"},
    {"id": "TKT-8815", "customer": CUSTOMERS[1], "issue": "Platform outage caused 4h downtime for VIP client", "severity": "high"},
    {"id": "TKT-8820", "customer": CUSTOMERS[2], "issue": "Data loss during migration, enterprise SLA breached", "severity": "critical"},
]

COMPENSATION_TIERS = {
    "low": {"credit": 25, "description": "Store credit"},
    "high": {"credit": 500, "description": "Service credit + priority support upgrade"},
    "critical": {"credit": 15000, "description": "Full SLA penalty + dedicated account manager"},
}

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="salesforce-prod",
    action="standard_complaint",
    params_fn=lambda ticket_id, customer_name, customer_email, issue, resolution, credit_amount: {
        "ticket_id": ticket_id,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "issue": issue,
        "resolution": resolution,
        "credit_amount_usd": credit_amount,
    },
)
def resolve_standard_complaint(ticket_id: str, customer_name: str,
                               customer_email: str, issue: str,
                               resolution: str, credit_amount: int) -> dict:
    """
    Resolve a standard customer complaint with small credit.
    Auto-approved -- low risk, routine resolution.
    """
    return {"resolved": True, "ticket": ticket_id, "credit": credit_amount}


@kit.requires_approval(
    connection="salesforce-prod",
    action="vip_complaint",
    params_fn=lambda ticket_id, customer_name, customer_email, account_id, issue, resolution, credit_amount: {
        "ticket_id": ticket_id,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "account_id": account_id,
        "issue": issue,
        "proposed_resolution": resolution,
        "credit_amount_usd": credit_amount,
    },
)
def resolve_vip_complaint(ticket_id: str, customer_name: str,
                          customer_email: str, account_id: str,
                          issue: str, resolution: str,
                          credit_amount: int) -> dict:
    """
    Resolve a VIP customer complaint.
    Requires CS Manager approval -- high-value relationship.
    """
    return {"resolved": True, "ticket": ticket_id, "credit": credit_amount}


@kit.requires_approval(
    connection="stripe-prod",
    action="large_compensation",
    params_fn=lambda ticket_id, customer_name, customer_email, account_id, issue, compensation_amount, compensation_description: {
        "ticket_id": ticket_id,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "account_id": account_id,
        "issue": issue,
        "compensation_amount_usd": compensation_amount,
        "compensation_description": compensation_description,
    },
)
def issue_large_compensation(ticket_id: str, customer_name: str,
                             customer_email: str, account_id: str,
                             issue: str, compensation_amount: int,
                             compensation_description: str) -> dict:
    """
    Issue large compensation (>= $5,000).
    Requires both CFO and Legal Counsel approval (all_of_n).
    """
    return {"compensated": True, "ticket": ticket_id, "amount": compensation_amount}


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Support Escalation Agent Demo")
    print("="*60)

    # Scenario 1: Standard complaint -- auto-approved
    scenario("Scenario 1: Standard complaint ($25 credit) -- auto-approved")
    t = TICKETS[0]
    comp = COMPENSATION_TIERS["low"]
    try:
        result = resolve_standard_complaint(
            t["id"], t["customer"]["name"], t["customer"]["email"],
            t["issue"], "Expedited reshipment + store credit", comp["credit"],
        )
        print(f"  Resolved {result['ticket']}: ${result['credit']} credit issued")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 2: VIP complaint -- CS Manager approval
    scenario("Scenario 2: VIP complaint ($500 credit) -- CS Manager required")
    t = TICKETS[1]
    comp = COMPENSATION_TIERS["high"]
    try:
        result = resolve_vip_complaint(
            t["id"], t["customer"]["name"], t["customer"]["email"],
            t["customer"]["account_id"], t["issue"],
            "Service credit + 3-month priority support upgrade", comp["credit"],
        )
        print(f"  Resolved {result['ticket']}: ${result['credit']} credit issued")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 3: Large compensation -- CFO + Legal (all_of_n)
    scenario("Scenario 3: Large compensation ($15,000) -- CFO + Legal required")
    t = TICKETS[2]
    comp = COMPENSATION_TIERS["critical"]
    print("  Both CFO and Legal Counsel must approve.")
    try:
        result = issue_large_compensation(
            t["id"], t["customer"]["name"], t["customer"]["email"],
            t["customer"]["account_id"], t["issue"],
            comp["credit"], comp["description"],
        )
        print(f"  Compensation issued for {result['ticket']}: ${result['amount']:,}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

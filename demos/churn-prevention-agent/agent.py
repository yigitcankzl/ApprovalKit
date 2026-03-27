"""
Demo Agent — Churn Prevention Agent
=====================================
Simulates an AI agent that detects at-risk customers and offers
retention incentives with tiered approval for discount levels.

Rule configuration (set up via dashboard or setup_rules.py):

  stripe-prod : credit
    discount <= 10%          -> no rule  (auto-approved)
    discount 11% - 30%       -> any_one  [manager]
    custom discount          -> specific [ceo]
    custom package            -> all_of_n [ceo, cfo]

  salesforce-prod : update_case
    retention case update    -> any_one  [cs_manager]

  gmail-prod : send_email
    retention offers         -> no rule  (auto-approved)

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/churn-prevention-agent/agent.py
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
    user_id="auth0|churn_prevention_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

AT_RISK_CUSTOMERS = [
    {
        "name": "RetailPro",
        "email": "admin@retailpro.com",
        "plan": "business",
        "mrr": 99,
        "risk_score": 0.72,
        "signals": ["usage_drop_40pct", "support_tickets_up", "missed_login_14d"],
        "months_active": 18,
    },
    {
        "name": "DesignHub",
        "email": "billing@designhub.io",
        "plan": "pro",
        "mrr": 29,
        "risk_score": 0.85,
        "signals": ["competitor_eval", "downgrade_inquiry", "usage_drop_60pct"],
        "months_active": 8,
    },
    {
        "name": "LogiCorp",
        "email": "ops@logicorp.co",
        "plan": "business",
        "mrr": 99,
        "risk_score": 0.91,
        "signals": ["cancellation_request", "exec_sponsor_left", "usage_drop_80pct"],
        "months_active": 36,
    },
    {
        "name": "EnterprisePlus",
        "email": "procurement@enterpriseplus.com",
        "plan": "enterprise",
        "mrr": 8500,
        "risk_score": 0.68,
        "signals": ["contract_renewal_90d", "budget_review", "competitor_demo"],
        "months_active": 24,
    },
]

DISCOUNT_TIERS = {
    "small": {"pct": 10, "label": "10% discount (3 months)", "duration_months": 3},
    "medium": {"pct": 20, "label": "20% discount (6 months)", "duration_months": 6},
    "large": {"pct": 30, "label": "30% discount (12 months)", "duration_months": 12},
    "custom": {"pct": None, "label": "Custom retention package", "duration_months": None},
}

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="stripe-prod",
    action="credit",
    params_fn=lambda customer_email, customer_name, discount_pct, duration_months, mrr, reason: {
        "customer_email": customer_email,
        "customer_name": customer_name,
        "discount_percent": discount_pct,
        "duration_months": duration_months,
        "current_mrr_usd": mrr,
        "monthly_credit_usd": round(mrr * discount_pct / 100),
        "total_credit_usd": round(mrr * discount_pct / 100 * duration_months),
        "reason": reason,
    },
)
def offer_discount(customer_email: str, customer_name: str, discount_pct: int, duration_months: int, mrr: int, reason: str) -> dict:
    """
    Offer a retention discount to an at-risk customer.
    Auto-approved for <=10%, manager for 11-30%, CEO for custom.
    Token Vault applies the credit after approval.
    """
    return {"customer": customer_name, "discount": discount_pct, "duration": duration_months}


@kit.requires_approval(
    connection="stripe-prod",
    action="credit",
    params_fn=lambda customer_email, customer_name, package_details, mrr, annual_value: {
        "customer_email": customer_email,
        "customer_name": customer_name,
        "custom_package": True,
        "package_details": package_details,
        "current_mrr_usd": mrr,
        "annual_contract_value_usd": annual_value,
    },
)
def create_custom_package(customer_email: str, customer_name: str, package_details: dict, mrr: int, annual_value: int) -> dict:
    """
    Create a fully custom retention package for high-value accounts.
    Requires both CEO and CFO approval (all_of_n).
    """
    return {"customer": customer_name, "package": package_details}


@kit.requires_approval(
    connection="salesforce-prod",
    action="update_case",
    params_fn=lambda case_id, customer_name, status, notes, risk_score: {
        "case_id": case_id,
        "customer_name": customer_name,
        "status": status,
        "notes": notes,
        "risk_score": risk_score,
    },
)
def update_retention_case(case_id: str, customer_name: str, status: str, notes: str, risk_score: float) -> dict:
    """Update a Salesforce retention case."""
    return {"case_id": case_id, "status": status}


@kit.requires_approval(
    connection="gmail-prod",
    action="send_email",
    params_fn=lambda recipient, subject, body: {
        "to": recipient,
        "subject": subject,
        "body": body,
    },
)
def send_retention_email(recipient: str, subject: str, body: str) -> dict:
    """Send a retention offer email to the customer."""
    return {"sent_to": recipient}


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Churn Prevention Agent Demo")
    print("="*60)

    # Scenario 1: Small discount — auto-approved
    scenario("Scenario 1: 10% discount for RetailPro — auto-approved")
    cust = AT_RISK_CUSTOMERS[0]
    tier = DISCOUNT_TIERS["small"]
    print(f"  Risk score: {cust['risk_score']} | Signals: {', '.join(cust['signals'])}")
    try:
        result = offer_discount(
            cust["email"], cust["name"], tier["pct"], tier["duration_months"],
            cust["mrr"], "Usage drop and support escalation"
        )
        fp = result["final_params"]
        print(f"  Offered {fp['discount_percent']}% discount to {fp['customer_name']}")
        print(f"  Monthly credit: ${fp['monthly_credit_usd']} for {fp['duration_months']} months")
        print(f"  Total credit: ${fp['total_credit_usd']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 2: Medium discount — manager approval
    scenario("Scenario 2: 20% discount for DesignHub — manager required")
    cust = AT_RISK_CUSTOMERS[1]
    tier = DISCOUNT_TIERS["medium"]
    print(f"  Risk score: {cust['risk_score']} | Signals: {', '.join(cust['signals'])}")
    try:
        result = offer_discount(
            cust["email"], cust["name"], tier["pct"], tier["duration_months"],
            cust["mrr"], "Competitor evaluation in progress"
        )
        fp = result["final_params"]
        print(f"  Offered {fp['discount_percent']}% discount to {fp['customer_name']}")
        print(f"  Total credit: ${fp['total_credit_usd']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 3: Large discount — manager approval (boundary)
    scenario("Scenario 3: 30% discount for LogiCorp — manager required")
    cust = AT_RISK_CUSTOMERS[2]
    tier = DISCOUNT_TIERS["large"]
    print(f"  Risk score: {cust['risk_score']} | Signals: {', '.join(cust['signals'])}")
    print(f"  Long-tenure customer ({cust['months_active']} months) requesting cancellation.")
    try:
        result = offer_discount(
            cust["email"], cust["name"], tier["pct"], tier["duration_months"],
            cust["mrr"], "Cancellation request — exec sponsor departure"
        )
        fp = result["final_params"]
        print(f"  Offered {fp['discount_percent']}% discount to {fp['customer_name']}")
        print(f"  Total credit: ${fp['total_credit_usd']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 4: Custom package for enterprise — CEO + CFO required
    scenario("Scenario 4: Custom package for EnterprisePlus — CEO + CFO required")
    cust = AT_RISK_CUSTOMERS[3]
    print(f"  Risk score: {cust['risk_score']} | MRR: ${cust['mrr']}")
    print(f"  Signals: {', '.join(cust['signals'])}")
    print(f"  Both CEO and CFO must approve this custom retention package.")
    package = {
        "discount_pct": 25,
        "duration_months": 12,
        "dedicated_tam": True,
        "custom_sla": "99.99% uptime",
        "additional_seats": 50,
        "training_hours": 40,
    }
    try:
        result = create_custom_package(
            cust["email"], cust["name"], package,
            cust["mrr"], cust["mrr"] * 12
        )
        fp = result["final_params"]
        print(f"  Custom package created for {fp['customer_name']}")
        print(f"  Annual value at risk: ${fp['annual_contract_value_usd']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 5: Update Salesforce retention case — cs_manager approval
    scenario("Scenario 5: Update Salesforce case — cs_manager approval")
    try:
        result = update_retention_case(
            "RET-00892", "LogiCorp", "Offer Sent",
            "30% discount for 12 months offered. Awaiting customer response. "
            "Exec sponsor replacement identified.",
            0.91
        )
        fp = result["final_params"]
        print(f"  Case {fp['case_id']} updated: {fp['status']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 6: Retention email — auto-approved
    scenario("Scenario 6: Retention offer email — auto-approved")
    cust = AT_RISK_CUSTOMERS[1]
    try:
        result = send_retention_email(
            cust["email"],
            "We want to keep you — here's a special offer",
            f"Hi {cust['name']},\n\nWe noticed you've been exploring other options "
            f"and we'd love to keep you on board. We're offering you a 20% discount "
            f"for the next 6 months on your Pro plan.\n\n"
            f"That's ${round(cust['mrr'] * 0.2)} off every month.\n\n"
            f"Reply to this email or schedule a call to discuss.\n\nCustomer Success Team"
        )
        print(f"  Retention email sent to {result['final_params']['to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

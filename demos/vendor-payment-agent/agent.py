"""
Demo Agent — Vendor Payment Agent
===================================
Simulates an AI agent that manages vendor payments with tiered
approval based on amount and vendor trust level.

Rule configuration (set up via dashboard or setup_rules.py):

  stripe-prod : vendor_payment
    amount < $1,000         -> no rule  (auto-approved)
    amount $1,000 - $10,000 -> any_one  [finance_manager]
    amount >= $10,000       -> all_of_n [cfo, ceo]
    new_vendor = true       -> specific [finance_manager]  (always requires review)

  slack-prod : send_message
    payment notifications   -> any_one  [team_lead]

  gmail-prod : send_email
    payment confirmations   -> no rule  (auto-approved)

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/vendor-payment-agent/agent.py
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
    user_id="auth0|vendor_payment_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

VENDORS = [
    {"name": "CloudHost", "id": "VND-001", "email": "billing@cloudhost.io", "is_new": False, "category": "infrastructure"},
    {"name": "DataCorp", "id": "VND-002", "email": "invoices@datacorp.com", "is_new": False, "category": "data_services"},
    {"name": "NewTech", "id": "VND-003", "email": "ar@newtech.dev", "is_new": True, "category": "software"},
    {"name": "OfficeMax", "id": "VND-004", "email": "orders@officemax.com", "is_new": False, "category": "supplies"},
]

PENDING_INVOICES = [
    {"vendor": "OfficeMax", "vendor_id": "VND-004", "invoice": "OM-88421", "amount": 340, "description": "Q1 office supply order"},
    {"vendor": "CloudHost", "vendor_id": "VND-001", "invoice": "CH-12055", "amount": 4800, "description": "March hosting — production cluster"},
    {"vendor": "DataCorp", "vendor_id": "VND-002", "invoice": "DC-7891", "amount": 25000, "description": "Annual data enrichment license"},
    {"vendor": "NewTech", "vendor_id": "VND-003", "invoice": "NT-0001", "amount": 1200, "description": "Developer tooling pilot — 3 month license"},
]

PAYMENT_TERMS = {
    "net_30": "Net 30 days",
    "net_60": "Net 60 days",
    "due_on_receipt": "Due on receipt",
}

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="stripe-prod",
    action="vendor_payment",
    params_fn=lambda amount, vendor_name, vendor_id, invoice_id, description, is_new_vendor: {
        "amount_usd": amount,
        "vendor_name": vendor_name,
        "vendor_id": vendor_id,
        "invoice_id": invoice_id,
        "description": description,
        "is_new_vendor": is_new_vendor,
    },
)
def pay_vendor(amount: int, vendor_name: str, vendor_id: str, invoice_id: str, description: str, is_new_vendor: bool) -> dict:
    """
    Process a vendor payment.
    Auto-approved under $1,000 (existing vendors only).
    Finance manager for $1k-$10k or new vendors.
    CFO + CEO for $10k+.
    Token Vault executes the payment after approval.
    """
    return {"paid": amount, "vendor": vendor_name, "invoice_id": invoice_id}


@kit.requires_approval(
    connection="slack-prod",
    action="send_message",
    params_fn=lambda channel, message: {
        "channel": channel,
        "message": message,
    },
)
def notify_slack(channel: str, message: str) -> dict:
    """Post a payment notification to Slack."""
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
def send_payment_confirmation(recipient: str, subject: str, body: str) -> dict:
    """Send a payment confirmation email to the vendor."""
    return {"sent_to": recipient}


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Vendor Payment Agent Demo")
    print("="*60)

    # Scenario 1: Small payment to existing vendor — auto-approved
    scenario("Scenario 1: Office supplies ($340) — auto-approved")
    inv = PENDING_INVOICES[0]
    vendor = VENDORS[3]
    try:
        result = pay_vendor(
            inv["amount"], inv["vendor"], inv["vendor_id"],
            inv["invoice"], inv["description"], vendor["is_new"]
        )
        fp = result["final_params"]
        print(f"  Paid ${fp['amount_usd']} to {fp['vendor_name']} ({fp['invoice_id']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 2: Medium payment — finance_manager approval
    scenario("Scenario 2: Hosting invoice ($4,800) — finance_manager required")
    inv = PENDING_INVOICES[1]
    vendor = VENDORS[0]
    try:
        result = pay_vendor(
            inv["amount"], inv["vendor"], inv["vendor_id"],
            inv["invoice"], inv["description"], vendor["is_new"]
        )
        fp = result["final_params"]
        print(f"  Paid ${fp['amount_usd']} to {fp['vendor_name']} ({fp['invoice_id']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 3: Large payment — CFO + CEO approval
    scenario("Scenario 3: Annual license ($25,000) — CFO + CEO required")
    inv = PENDING_INVOICES[2]
    vendor = VENDORS[1]
    print(f"  Both CFO and CEO must approve this payment.")
    try:
        result = pay_vendor(
            inv["amount"], inv["vendor"], inv["vendor_id"],
            inv["invoice"], inv["description"], vendor["is_new"]
        )
        fp = result["final_params"]
        print(f"  Paid ${fp['amount_usd']} to {fp['vendor_name']} ({fp['invoice_id']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 4: New vendor payment — always requires finance_manager review
    scenario("Scenario 4: New vendor ($1,200) — finance_manager required (new vendor)")
    inv = PENDING_INVOICES[3]
    vendor = VENDORS[2]
    print(f"  NEW VENDOR FLAG: {vendor['name']} has not been paid before.")
    try:
        result = pay_vendor(
            inv["amount"], inv["vendor"], inv["vendor_id"],
            inv["invoice"], inv["description"], vendor["is_new"]
        )
        fp = result["final_params"]
        print(f"  Paid ${fp['amount_usd']} to {fp['vendor_name']} ({fp['invoice_id']})")
        print(f"  New vendor flag: {fp['is_new_vendor']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 5: Slack notification for large payment
    scenario("Scenario 5: Slack notification — team_lead approval")
    try:
        result = notify_slack(
            "#vendor-payments",
            "Large payment processed: $25,000 to DataCorp (DC-7891) — Annual data enrichment license"
        )
        print(f"  Posted to {result['final_params']['channel']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 6: Payment confirmation email — auto-approved
    scenario("Scenario 6: Payment confirmation email — auto-approved")
    try:
        result = send_payment_confirmation(
            "billing@cloudhost.io",
            "Payment Confirmation: CH-12055",
            "Dear CloudHost,\n\nPayment of $4,800 for invoice CH-12055 "
            "(March hosting — production cluster) has been processed.\n\n"
            "Payment reference: PAY-20260327-001\n\nAccounts Payable"
        )
        print(f"  Confirmation sent to {result['final_params']['to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

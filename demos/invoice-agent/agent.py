"""
Demo Agent — Invoice Agent
==========================
Simulates an AI invoice management agent that sends invoices,
follows up on overdue accounts, and escalates to legal collections.
Every high-risk action is gated behind an ApprovalKit rule.

Rule configuration (set up via dashboard or setup_rules.py):

  stripe-prod : charge
    invoice amount < $1000  -> no rule  (auto-approved)
    invoice amount >= $1000 -> any_one  [finance_manager]

  gmail-prod : send_email
    overdue reminder        -> no rule  (auto-approved)
    legal notice            -> all_of_n [cfo, legal_counsel]

  salesforce-prod : update_case
    case update             -> any_one  [finance_manager]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/invoice-agent/agent.py
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
    user_id="auth0|invoice_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

INVOICE_TEMPLATES = {
    "standard": {"subject": "Invoice #{id}", "footer": "Payment due within 30 days."},
    "recurring": {"subject": "Monthly Invoice #{id}", "footer": "Auto-billed on the 1st."},
    "final_notice": {"subject": "FINAL NOTICE — Invoice #{id}", "footer": "Immediate payment required."},
}

CLIENTS = [
    {"name": "Acme Corp", "email": "billing@acme.com", "tier": "enterprise"},
    {"name": "Widgets Inc", "email": "ap@widgets.io", "tier": "standard"},
    {"name": "MegaTech", "email": "finance@megatech.co", "tier": "enterprise"},
    {"name": "StartupXYZ", "email": "hello@startupxyz.com", "tier": "startup"},
]

OVERDUE_ACCOUNTS = [
    {"client": "Widgets Inc", "invoice_id": "INV-2041", "amount": 4200, "days_overdue": 15},
    {"client": "StartupXYZ", "invoice_id": "INV-2038", "amount": 850, "days_overdue": 45},
    {"client": "OldCo LLC", "invoice_id": "INV-1987", "amount": 12750, "days_overdue": 120},
]

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="stripe-prod",
    action="charge",
    params_fn=lambda amount, client_email, invoice_id, description: {
        "amount_usd": amount,
        "customer": client_email,
        "invoice_id": invoice_id,
        "description": description,
    },
)
def send_invoice(amount: int, client_email: str, invoice_id: str, description: str) -> dict:
    """
    Send an invoice and charge the client via Stripe.
    Auto-approved under $1000; finance_manager required above.
    Token Vault executes the actual charge after approval.
    """
    return {"invoiced": amount, "client": client_email, "invoice_id": invoice_id}


@kit.requires_approval(
    connection="gmail-prod",
    action="send_email",
    params_fn=lambda recipient, subject, body, invoice_id: {
        "to": recipient,
        "subject": subject,
        "body": body,
        "invoice_id": invoice_id,
    },
)
def send_overdue_reminder(recipient: str, subject: str, body: str, invoice_id: str) -> dict:
    """
    Send an overdue payment reminder via Gmail.
    Auto-approved for standard reminders.
    """
    return {"sent_to": recipient, "invoice_id": invoice_id}


@kit.requires_approval(
    connection="gmail-prod",
    action="send_email",
    params_fn=lambda recipient, subject, body, invoice_id, amount: {
        "to": recipient,
        "subject": subject,
        "body": body,
        "invoice_id": invoice_id,
        "amount_usd": amount,
        "legal_action": True,
    },
)
def initiate_legal_collection(recipient: str, subject: str, body: str, invoice_id: str, amount: int) -> dict:
    """
    Initiate legal collection proceedings via formal notice.
    Requires both CFO and Legal Counsel approval (all_of_n).
    """
    return {"legal_notice_sent": recipient, "invoice_id": invoice_id, "amount": amount}


@kit.requires_approval(
    connection="salesforce-prod",
    action="update_case",
    params_fn=lambda case_id, status, notes: {
        "case_id": case_id,
        "status": status,
        "notes": notes,
    },
)
def update_salesforce_case(case_id: str, status: str, notes: str) -> dict:
    """Update a Salesforce case with collection status."""
    return {"case_id": case_id, "status": status}


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Invoice Agent Demo")
    print("="*60)

    # Scenario 1: Small invoice — auto-approved
    scenario("Scenario 1: Small invoice ($750) — auto-approved")
    client = CLIENTS[1]
    try:
        result = send_invoice(
            750, client["email"], "INV-2055",
            f"Consulting services for {client['name']}"
        )
        print(f"  Invoice sent: ${result['final_params']['amount_usd']} to {client['email']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 2: Large invoice — finance_manager approval
    scenario("Scenario 2: Large invoice ($8,500) — finance_manager required")
    client = CLIENTS[0]
    try:
        result = send_invoice(
            8500, client["email"], "INV-2056",
            f"Enterprise platform license for {client['name']}"
        )
        print(f"  Invoice sent: ${result['final_params']['amount_usd']} to {client['email']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 3: Overdue reminder — auto-approved
    scenario("Scenario 3: Overdue reminder (15 days) — auto-approved")
    overdue = OVERDUE_ACCOUNTS[0]
    try:
        result = send_overdue_reminder(
            "ap@widgets.io",
            f"Overdue: {overdue['invoice_id']} — {overdue['days_overdue']} days past due",
            f"Dear Widgets Inc,\n\nInvoice {overdue['invoice_id']} for ${overdue['amount']} "
            f"is now {overdue['days_overdue']} days overdue. Please remit payment.",
            overdue["invoice_id"],
        )
        print(f"  Reminder sent to {result['final_params']['to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 4: Legal collection — CFO + Legal Counsel required
    scenario("Scenario 4: Legal collection ($12,750) — CFO + Legal Counsel required")
    overdue = OVERDUE_ACCOUNTS[2]
    print("  Both CFO and Legal Counsel must approve.")
    try:
        result = initiate_legal_collection(
            "legal@oldco-llc.com",
            f"FINAL NOTICE — {overdue['invoice_id']}",
            f"This constitutes formal notice that invoice {overdue['invoice_id']} "
            f"for ${overdue['amount']} is {overdue['days_overdue']} days overdue. "
            f"Legal proceedings will commence in 10 business days.",
            overdue["invoice_id"],
            overdue["amount"],
        )
        print(f"  Legal notice sent to {result['final_params']['to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 5: Update Salesforce case
    scenario("Scenario 5: Update Salesforce case — finance_manager approval")
    try:
        result = update_salesforce_case(
            "CASE-00421", "Escalated",
            "Account 120 days overdue. Legal collection initiated."
        )
        print(f"  Case {result['final_params']['case_id']} updated to {result['final_params']['status']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

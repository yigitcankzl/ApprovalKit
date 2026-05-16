"""
Demo Agent — Expense Approval Agent
====================================
Simulates an AI expense management agent that processes employee
expense reports with tiered approval based on amount.

Rule configuration (set up via dashboard or setup_rules.py):

  stripe-prod : charge
    amount < $500           -> no rule  (auto-approved)
    amount $500 - $5000     -> any_one  [manager]
    amount >= $5000         -> specific [cfo]

  slack-prod : send_message
    expense notifications   -> any_one  [team_lead]

  gmail-prod : send_email
    receipt confirmations   -> no rule  (auto-approved)

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python examples/expense-agent/agent.py
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
    user_id="auth0|expense_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

EXPENSE_CATEGORIES = {
    "office_supplies": {"label": "Office Supplies", "default_limit": 200},
    "equipment": {"label": "Equipment", "default_limit": 2000},
    "travel": {"label": "Travel", "default_limit": 5000},
    "team_event": {"label": "Team Event", "default_limit": 3000},
}

EMPLOYEES = [
    {"name": "Sarah Chen", "email": "sarah@company.com", "department": "Engineering", "manager": "Mike Torres"},
    {"name": "James Park", "email": "james@company.com", "department": "Sales", "manager": "Lisa Wong"},
    {"name": "Maria Lopez", "email": "maria@company.com", "department": "Marketing", "manager": "Lisa Wong"},
    {"name": "Alex Kim", "email": "alex@company.com", "department": "Engineering", "manager": "Mike Torres"},
]

PENDING_EXPENSES = [
    {"employee": "Sarah Chen", "category": "office_supplies", "amount": 89, "description": "Ergonomic keyboard and mouse pad", "receipt": "REC-4401"},
    {"employee": "James Park", "category": "travel", "amount": 1850, "description": "Client visit flight + hotel — Chicago", "receipt": "REC-4402"},
    {"employee": "Maria Lopez", "category": "team_event", "amount": 4200, "description": "Q1 marketing team offsite venue", "receipt": "REC-4403"},
    {"employee": "Alex Kim", "category": "equipment", "amount": 7500, "description": "ML workstation with dual GPU", "receipt": "REC-4404"},
    {"employee": "Sarah Chen", "category": "travel", "amount": 320, "description": "Uber rides — conference week", "receipt": "REC-4405"},
]

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="stripe-prod",
    action="charge",
    params_fn=lambda amount, employee_email, category, description, receipt_id: {
        "amount_usd": amount,
        "employee": employee_email,
        "category": category,
        "description": description,
        "receipt_id": receipt_id,
    },
)
def submit_expense(amount: int, employee_email: str, category: str, description: str, receipt_id: str) -> dict:
    """
    Submit and process an expense reimbursement.
    Auto-approved under $500, manager $500-$5000, CFO $5000+.
    Token Vault executes the reimbursement after approval.
    """
    return {"reimbursed": amount, "employee": employee_email, "receipt_id": receipt_id}


@kit.requires_approval(
    connection="slack-prod",
    action="send_message",
    params_fn=lambda channel, message: {
        "channel": channel,
        "message": message,
    },
)
def notify_slack(channel: str, message: str) -> dict:
    """Post an expense notification to Slack."""
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
def send_receipt_confirmation(recipient: str, subject: str, body: str) -> dict:
    """Send a receipt confirmation email to the employee."""
    return {"sent_to": recipient}


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Expense Approval Agent Demo")
    print("="*60)

    # Scenario 1: Small expense — auto-approved
    scenario("Scenario 1: Office supplies ($89) — auto-approved")
    exp = PENDING_EXPENSES[0]
    emp = EMPLOYEES[0]
    try:
        result = submit_expense(
            exp["amount"], emp["email"], exp["category"],
            exp["description"], exp["receipt"]
        )
        print(f"  Expense approved: ${result['final_params']['amount_usd']} for {emp['name']}")
        print(f"  Category: {EXPENSE_CATEGORIES[exp['category']]['label']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 2: Travel expense — manager approval
    scenario("Scenario 2: Travel ($1,850) — manager approval required")
    exp = PENDING_EXPENSES[1]
    emp = EMPLOYEES[1]
    print(f"  Manager: {emp['manager']}")
    try:
        result = submit_expense(
            exp["amount"], emp["email"], exp["category"],
            exp["description"], exp["receipt"]
        )
        print(f"  Expense approved: ${result['final_params']['amount_usd']} for {emp['name']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 3: Team event — manager approval (near limit)
    scenario("Scenario 3: Team event ($4,200) — manager approval required")
    exp = PENDING_EXPENSES[2]
    emp = EMPLOYEES[2]
    print(f"  Manager: {emp['manager']}")
    try:
        result = submit_expense(
            exp["amount"], emp["email"], exp["category"],
            exp["description"], exp["receipt"]
        )
        print(f"  Expense approved: ${result['final_params']['amount_usd']} for {emp['name']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 4: Equipment — CFO approval (over $5000)
    scenario("Scenario 4: ML workstation ($7,500) — CFO approval required")
    exp = PENDING_EXPENSES[3]
    emp = EMPLOYEES[3]
    print(f"  Amount exceeds $5,000 threshold. CFO must approve.")
    try:
        result = submit_expense(
            exp["amount"], emp["email"], exp["category"],
            exp["description"], exp["receipt"]
        )
        print(f"  Expense approved: ${result['final_params']['amount_usd']} for {emp['name']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 5: Slack notification
    scenario("Scenario 5: Slack notification — team_lead approval")
    try:
        result = notify_slack(
            "#expense-reports",
            "New high-value expense: Alex Kim — ML workstation ($7,500). Pending CFO approval."
        )
        print(f"  Posted to {result['final_params']['channel']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 6: Receipt confirmation email — auto-approved
    scenario("Scenario 6: Receipt confirmation email — auto-approved")
    try:
        result = send_receipt_confirmation(
            "sarah@company.com",
            "Expense Approved: REC-4401",
            "Hi Sarah,\n\nYour expense for 'Ergonomic keyboard and mouse pad' ($89) "
            "has been approved and reimbursement is being processed.\n\nFinance Team"
        )
        print(f"  Confirmation sent to {result['final_params']['to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

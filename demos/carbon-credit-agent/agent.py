"""
Demo Agent — Carbon Credit Agent
==================================
Simulates an AI agent that purchases carbon credits and manages
forward contracts for corporate sustainability programs.

Rule configuration (set up via dashboard or setup_rules.py):

  stripe-prod : charge
    amount < $10,000              -> no rule  (auto-approved)
    amount $10,000 - $50,000      -> any_one  [sustainability_lead]
    forward contract signing      -> all_of_n [cfo, sustainability_lead]

  slack-prod : send_message
    carbon credit notifications   -> any_one  [team_lead]

  gmail-prod : send_email
    purchase confirmations        -> no rule  (auto-approved)

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/carbon-credit-agent/agent.py
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
    user_id="auth0|carbon_credit_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

CARBON_REGISTRIES = [
    {"name": "Verra VCS", "id": "REG-VCS", "credit_type": "verified_carbon_standard"},
    {"name": "Gold Standard", "id": "REG-GS", "credit_type": "gold_standard_ver"},
    {"name": "American Carbon Registry", "id": "REG-ACR", "credit_type": "american_carbon"},
]

AVAILABLE_CREDITS = [
    {"project": "Amazon Reforestation", "registry": "Verra VCS", "vintage": 2025, "price_per_ton": 18, "tons_available": 5000},
    {"project": "India Solar Farm", "registry": "Gold Standard", "vintage": 2025, "price_per_ton": 22, "tons_available": 3000},
    {"project": "US Methane Capture", "registry": "American Carbon Registry", "vintage": 2026, "price_per_ton": 35, "tons_available": 2000},
    {"project": "Kenya Cookstoves", "registry": "Gold Standard", "vintage": 2025, "price_per_ton": 15, "tons_available": 10000},
]

COMPANY_EMISSIONS = {
    "annual_tons_co2": 12000,
    "offset_target_pct": 100,
    "credits_purchased_ytd": 4500,
    "credits_remaining": 7500,
    "budget_remaining_usd": 250000,
}

FORWARD_CONTRACT_TERMS = {
    "min_years": 3,
    "max_years": 10,
    "volume_discount_pct": 15,
    "price_lock_guarantee": True,
}

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="stripe-prod",
    action="charge",
    params_fn=lambda amount, tons, project, registry, vintage, price_per_ton: {
        "amount_usd": amount,
        "tons_co2": tons,
        "project": project,
        "registry": registry,
        "vintage": vintage,
        "price_per_ton_usd": price_per_ton,
    },
)
def purchase_credits(amount: int, tons: int, project: str, registry: str, vintage: int, price_per_ton: int) -> dict:
    """
    Purchase carbon credits from a verified registry.
    Auto-approved under $10,000; sustainability_lead for $10k-$50k.
    Token Vault executes the payment after approval.
    """
    return {"purchased_tons": tons, "amount": amount, "project": project}


@kit.requires_approval(
    connection="stripe-prod",
    action="charge",
    params_fn=lambda annual_amount, total_amount, tons_per_year, years, project, registry, price_per_ton: {
        "annual_amount_usd": annual_amount,
        "total_contract_value_usd": total_amount,
        "tons_co2_per_year": tons_per_year,
        "contract_years": years,
        "project": project,
        "registry": registry,
        "price_per_ton_usd": price_per_ton,
        "forward_contract": True,
        "price_lock": True,
    },
)
def sign_forward_contract(annual_amount: int, total_amount: int, tons_per_year: int, years: int, project: str, registry: str, price_per_ton: int) -> dict:
    """
    Sign a multi-year forward contract for carbon credits.
    Requires both CFO and sustainability_lead approval (all_of_n).
    """
    return {"years": years, "annual_tons": tons_per_year, "total_value": total_amount}


@kit.requires_approval(
    connection="slack-prod",
    action="send_message",
    params_fn=lambda channel, message: {
        "channel": channel,
        "message": message,
    },
)
def notify_slack(channel: str, message: str) -> dict:
    """Post a carbon credit notification to Slack."""
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
def send_purchase_confirmation(recipient: str, subject: str, body: str) -> dict:
    """Send a carbon credit purchase confirmation email."""
    return {"sent_to": recipient}


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Carbon Credit Agent Demo")
    print("="*60)
    print(f"\n  Company emissions: {COMPANY_EMISSIONS['annual_tons_co2']} tons CO2/year")
    print(f"  Credits purchased YTD: {COMPANY_EMISSIONS['credits_purchased_ytd']} tons")
    print(f"  Remaining to offset: {COMPANY_EMISSIONS['credits_remaining']} tons")
    print(f"  Budget remaining: ${COMPANY_EMISSIONS['budget_remaining_usd']:,}")

    # Scenario 1: Small purchase — auto-approved
    scenario("Scenario 1: Small credit purchase ($7,500) — auto-approved")
    credit = AVAILABLE_CREDITS[0]
    tons = 400
    amount = tons * credit["price_per_ton"]
    print(f"  Project: {credit['project']} ({credit['registry']})")
    print(f"  {tons} tons @ ${credit['price_per_ton']}/ton = ${amount}")
    try:
        result = purchase_credits(
            amount, tons, credit["project"], credit["registry"],
            credit["vintage"], credit["price_per_ton"]
        )
        fp = result["final_params"]
        print(f"  Purchased {fp['tons_co2']} tons from {fp['project']}")
        print(f"  Amount: ${fp['amount_usd']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 2: Medium purchase — sustainability_lead approval
    scenario("Scenario 2: Medium purchase ($33,000) — sustainability_lead required")
    credit = AVAILABLE_CREDITS[1]
    tons = 1500
    amount = tons * credit["price_per_ton"]
    print(f"  Project: {credit['project']} ({credit['registry']})")
    print(f"  {tons} tons @ ${credit['price_per_ton']}/ton = ${amount}")
    try:
        result = purchase_credits(
            amount, tons, credit["project"], credit["registry"],
            credit["vintage"], credit["price_per_ton"]
        )
        fp = result["final_params"]
        print(f"  Purchased {fp['tons_co2']} tons from {fp['project']}")
        print(f"  Amount: ${fp['amount_usd']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 3: Premium credits — sustainability_lead approval
    scenario("Scenario 3: Premium credits ($35,000) — sustainability_lead required")
    credit = AVAILABLE_CREDITS[2]
    tons = 1000
    amount = tons * credit["price_per_ton"]
    print(f"  Project: {credit['project']} ({credit['registry']})")
    print(f"  Vintage: {credit['vintage']} (future vintage premium)")
    print(f"  {tons} tons @ ${credit['price_per_ton']}/ton = ${amount}")
    try:
        result = purchase_credits(
            amount, tons, credit["project"], credit["registry"],
            credit["vintage"], credit["price_per_ton"]
        )
        fp = result["final_params"]
        print(f"  Purchased {fp['tons_co2']} tons from {fp['project']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 4: Forward contract — CFO + sustainability_lead required
    scenario("Scenario 4: 5-year forward contract — CFO + sustainability_lead required")
    credit = AVAILABLE_CREDITS[3]
    tons_per_year = 2000
    years = 5
    discounted_price = round(credit["price_per_ton"] * (1 - FORWARD_CONTRACT_TERMS["volume_discount_pct"] / 100))
    annual_amount = tons_per_year * discounted_price
    total_amount = annual_amount * years
    print(f"  Project: {credit['project']} ({credit['registry']})")
    print(f"  {tons_per_year} tons/year x {years} years = {tons_per_year * years} total tons")
    print(f"  Price: ${discounted_price}/ton (15% volume discount from ${credit['price_per_ton']})")
    print(f"  Annual: ${annual_amount:,} | Total: ${total_amount:,}")
    print(f"  Both CFO and sustainability_lead must approve.")
    try:
        result = sign_forward_contract(
            annual_amount, total_amount, tons_per_year, years,
            credit["project"], credit["registry"], discounted_price
        )
        fp = result["final_params"]
        print(f"  Forward contract signed: {fp['contract_years']} years")
        print(f"  {fp['tons_co2_per_year']} tons/year at ${fp['price_per_ton_usd']}/ton (locked)")
        print(f"  Total contract value: ${fp['total_contract_value_usd']:,}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 5: Slack notification
    scenario("Scenario 5: Slack notification — team_lead approval")
    try:
        result = notify_slack(
            "#sustainability",
            "Carbon offset update: 4,900 tons purchased YTD (65% of target). "
            "5-year forward contract pending for Kenya Cookstoves project (10,000 tons)."
        )
        print(f"  Posted to {result['final_params']['channel']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 6: Purchase confirmation email — auto-approved
    scenario("Scenario 6: Purchase confirmation email — auto-approved")
    try:
        result = send_purchase_confirmation(
            "sustainability@company.com",
            "Carbon Credit Purchase Confirmation — 400 tons VCS",
            "Purchase confirmed:\n\n"
            "  Project: Amazon Reforestation\n"
            "  Registry: Verra VCS\n"
            "  Volume: 400 tons CO2\n"
            "  Vintage: 2025\n"
            "  Amount: $7,200\n\n"
            "  Serial numbers will be delivered to your registry account within 48 hours.\n\n"
            "Sustainability Team"
        )
        print(f"  Confirmation sent to {result['final_params']['to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

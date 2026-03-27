"""
Demo Agent — Renewable Energy Procurement (Energy)
===================================================
Simulates an AI agent that handles renewable energy purchasing
with tiered approval based on commitment size.

Rule configuration:

  energy-procurement : purchase
    amount < 10000           -> no rule  (auto-approved)
    amount 10000-99999       -> any_one  [CFO]
    amount >= 100000         -> all_of_n [CEO, CFO]  (long_term_agreement)

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/renewable-energy-agent/agent.py
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
    user_id="auth0|renewable_energy_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

SUPPLIERS = {
    "SUP-E001": {"name": "SunPeak Solar Co.", "type": "solar", "region": "Southwest"},
    "SUP-E002": {"name": "WindFlow Energy", "type": "wind", "region": "Midwest"},
    "SUP-E003": {"name": "GreenGrid Consortium", "type": "mixed_renewable", "region": "National"},
}

PURCHASE_ORDERS = {
    "PO-001": {
        "supplier": "SUP-E001",
        "description": "Solar panel batch for rooftop installation",
        "amount_usd": 7500,
        "energy_type": "solar",
        "term_months": 0,
    },
    "PO-002": {
        "supplier": "SUP-E002",
        "description": "Wind energy credits Q2 2026",
        "amount_usd": 45000,
        "energy_type": "wind",
        "term_months": 3,
    },
    "PO-003": {
        "supplier": "SUP-E003",
        "description": "10-year renewable energy power purchase agreement",
        "amount_usd": 2800000,
        "energy_type": "mixed_renewable",
        "term_months": 120,
    },
}

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="energy-procurement",
    action="purchase",
    params_fn=lambda order_id: {
        "order_id": order_id,
        "supplier": SUPPLIERS[PURCHASE_ORDERS[order_id]["supplier"]]["name"],
        "description": PURCHASE_ORDERS[order_id]["description"],
        "amount_usd": PURCHASE_ORDERS[order_id]["amount_usd"],
        "energy_type": PURCHASE_ORDERS[order_id]["energy_type"],
        "type": "small_purchase",
    },
)
def process_small_purchase(order_id: str) -> dict:
    """
    Process a small energy purchase (< $10,000).
    Auto-approved -- within pre-authorized procurement budget.
    """
    order = PURCHASE_ORDERS[order_id]
    supplier = SUPPLIERS[order["supplier"]]
    return {
        "order_id": order_id,
        "supplier": supplier["name"],
        "amount_usd": order["amount_usd"],
        "status": "purchased",
    }


@kit.requires_approval(
    connection="energy-procurement",
    action="purchase",
    params_fn=lambda order_id: {
        "order_id": order_id,
        "supplier": SUPPLIERS[PURCHASE_ORDERS[order_id]["supplier"]]["name"],
        "description": PURCHASE_ORDERS[order_id]["description"],
        "amount_usd": PURCHASE_ORDERS[order_id]["amount_usd"],
        "energy_type": PURCHASE_ORDERS[order_id]["energy_type"],
        "term_months": PURCHASE_ORDERS[order_id]["term_months"],
        "type": "medium_purchase",
    },
)
def process_medium_purchase(order_id: str) -> dict:
    """
    Process a medium energy purchase ($10,000 - $99,999).
    Requires CFO approval.
    """
    order = PURCHASE_ORDERS[order_id]
    supplier = SUPPLIERS[order["supplier"]]
    return {
        "order_id": order_id,
        "supplier": supplier["name"],
        "amount_usd": order["amount_usd"],
        "status": "approved_and_ordered",
    }


@kit.requires_approval(
    connection="energy-procurement",
    action="purchase",
    params_fn=lambda order_id: {
        "order_id": order_id,
        "supplier": SUPPLIERS[PURCHASE_ORDERS[order_id]["supplier"]]["name"],
        "description": PURCHASE_ORDERS[order_id]["description"],
        "amount_usd": PURCHASE_ORDERS[order_id]["amount_usd"],
        "energy_type": PURCHASE_ORDERS[order_id]["energy_type"],
        "term_months": PURCHASE_ORDERS[order_id]["term_months"],
        "region": SUPPLIERS[PURCHASE_ORDERS[order_id]["supplier"]]["region"],
        "type": "long_term_agreement",
    },
)
def execute_long_term_agreement(order_id: str) -> dict:
    """
    Execute a long-term energy agreement (>= $100,000).
    Requires both CEO AND CFO approval (all_of_n).
    """
    order = PURCHASE_ORDERS[order_id]
    supplier = SUPPLIERS[order["supplier"]]
    return {
        "order_id": order_id,
        "supplier": supplier["name"],
        "amount_usd": order["amount_usd"],
        "term_months": order["term_months"],
        "status": "agreement_executed",
    }


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Renewable Energy Procurement Agent Demo")
    print("="*60)

    # -- Scenario 1: Small purchase -- auto-approved ---
    scenario("Scenario 1: Small purchase ($7,500 solar) -- auto-approved")
    try:
        result = process_small_purchase("PO-001")
        print(f"  Purchased from {result['supplier']}")
        print(f"  Amount: ${result['amount_usd']:,}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 2: Medium purchase -- CFO ---
    scenario("Scenario 2: Medium purchase ($45,000 wind) -- CFO approval")
    try:
        result = process_medium_purchase("PO-002")
        print(f"  Approved: {result['supplier']}")
        print(f"  Amount: ${result['amount_usd']:,}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 3: Long-term agreement -- CEO + CFO ---
    scenario("Scenario 3: Long-term PPA ($2.8M, 10yr) -- CEO + CFO required")
    print("  Both CEO and CFO must approve.")
    try:
        result = execute_long_term_agreement("PO-003")
        print(f"  Executed: {result['supplier']}")
        print(f"  Amount: ${result['amount_usd']:,}")
        print(f"  Term: {result['term_months']} months")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

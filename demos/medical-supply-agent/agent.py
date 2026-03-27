"""
Demo Agent -- Medical Supply Ordering
=======================================
Simulates an AI agent that manages medical supply orders: routine
consumables, specialized equipment, and large device purchases.
Each order tier has its own approval gate via ApprovalKit.

Rule configuration (set up via dashboard or setup_rules.py):

  stripe-prod : consumable
    consumables < $500     -> no rule  (auto-approved)

  stripe-prod : equipment
    equipment $500-$10k    -> specific [chief_doctor]

  stripe-prod : device_purchase
    devices >= $10k        -> all_of_n [chief_doctor, cfo]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/medical-supply-agent/agent.py
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
    user_id="auth0|medical_supply_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

DEPARTMENTS = [
    {"name": "Emergency", "code": "ER", "budget_remaining": 45000},
    {"name": "Cardiology", "code": "CARD", "budget_remaining": 120000},
    {"name": "Orthopedics", "code": "ORTH", "budget_remaining": 85000},
]

CONSUMABLES = [
    {"item": "Nitrile Gloves (case of 1000)", "sku": "CON-1001", "unit_price": 45, "category": "PPE"},
    {"item": "Saline IV Bags (box of 24)", "sku": "CON-1042", "unit_price": 72, "category": "fluids"},
    {"item": "Surgical Masks N95 (box of 50)", "sku": "CON-1015", "unit_price": 38, "category": "PPE"},
]

EQUIPMENT = [
    {"item": "Portable Pulse Oximeter", "sku": "EQP-2010", "unit_price": 1200, "category": "monitoring"},
    {"item": "IV Infusion Pump", "sku": "EQP-2035", "unit_price": 4500, "category": "infusion"},
    {"item": "Surgical Light (mobile)", "sku": "EQP-2041", "unit_price": 8500, "category": "surgical"},
]

DEVICES = [
    {"item": "Portable Ultrasound System", "sku": "DEV-3001", "unit_price": 35000, "category": "imaging"},
    {"item": "Patient Monitor (12-lead)", "sku": "DEV-3015", "unit_price": 22000, "category": "monitoring"},
    {"item": "Ventilator (ICU-grade)", "sku": "DEV-3022", "unit_price": 48000, "category": "respiratory"},
]

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="stripe-prod",
    action="consumable",
    params_fn=lambda item_name, sku, quantity, unit_price, department, category: {
        "item_name": item_name,
        "sku": sku,
        "quantity": quantity,
        "unit_price_usd": unit_price,
        "total_usd": quantity * unit_price,
        "department": department,
        "category": category,
    },
)
def order_consumable(item_name: str, sku: str, quantity: int,
                     unit_price: int, department: str, category: str) -> dict:
    """
    Order routine consumable supplies.
    Auto-approved -- low cost, recurring need.
    """
    total = quantity * unit_price
    return {"ordered": True, "item": item_name, "quantity": quantity, "total": total}


@kit.requires_approval(
    connection="stripe-prod",
    action="equipment",
    params_fn=lambda item_name, sku, quantity, unit_price, department, justification: {
        "item_name": item_name,
        "sku": sku,
        "quantity": quantity,
        "unit_price_usd": unit_price,
        "total_usd": quantity * unit_price,
        "department": department,
        "clinical_justification": justification,
    },
)
def order_equipment(item_name: str, sku: str, quantity: int,
                    unit_price: int, department: str,
                    justification: str) -> dict:
    """
    Order specialized medical equipment.
    Requires Chief Doctor approval.
    """
    total = quantity * unit_price
    return {"ordered": True, "item": item_name, "quantity": quantity, "total": total}


@kit.requires_approval(
    connection="stripe-prod",
    action="device_purchase",
    params_fn=lambda item_name, sku, quantity, unit_price, department, justification, vendor: {
        "item_name": item_name,
        "sku": sku,
        "quantity": quantity,
        "unit_price_usd": unit_price,
        "total_usd": quantity * unit_price,
        "department": department,
        "clinical_justification": justification,
        "vendor": vendor,
    },
)
def purchase_device(item_name: str, sku: str, quantity: int,
                    unit_price: int, department: str,
                    justification: str, vendor: str) -> dict:
    """
    Purchase major medical device.
    Requires both Chief Doctor and CFO approval (all_of_n).
    """
    total = quantity * unit_price
    return {"purchased": True, "item": item_name, "quantity": quantity, "total": total}


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Medical Supply Ordering Agent Demo")
    print("="*60)

    # Scenario 1: Consumable order -- auto-approved
    scenario("Scenario 1: Consumable order ($360) -- auto-approved")
    item = CONSUMABLES[0]
    dept = DEPARTMENTS[0]
    qty = 8
    try:
        result = order_consumable(
            item["item"], item["sku"], qty,
            item["unit_price"], dept["name"], item["category"],
        )
        print(f"  Ordered {result['quantity']}x {result['item']}: ${result['total']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 2: Equipment order -- Chief Doctor approval
    scenario("Scenario 2: Equipment order ($4,500) -- Chief Doctor required")
    item = EQUIPMENT[1]
    dept = DEPARTMENTS[1]
    try:
        result = order_equipment(
            item["item"], item["sku"], 1,
            item["unit_price"], dept["name"],
            "Replacement for malfunctioning unit in cardiac care wing",
        )
        print(f"  Ordered {result['quantity']}x {result['item']}: ${result['total']:,}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 3: Device purchase -- Chief Doctor + CFO (all_of_n)
    scenario("Scenario 3: Device purchase ($48,000) -- Chief Doctor + CFO required")
    item = DEVICES[2]
    dept = DEPARTMENTS[0]
    print("  Both Chief Doctor and CFO must approve.")
    try:
        result = purchase_device(
            item["item"], item["sku"], 1,
            item["unit_price"], dept["name"],
            "ICU expansion requires additional ventilator capacity",
            "MedEquip International",
        )
        print(f"  Purchased {result['quantity']}x {result['item']}: ${result['total']:,}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

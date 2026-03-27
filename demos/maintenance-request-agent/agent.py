"""
Demo Agent — Maintenance Request (Real Estate)
===============================================
Simulates an AI property management agent that handles maintenance
requests with cost-based tiers and an emergency bypass.

Rule configuration:

  property-mgmt : maintenance
    amount < 500             -> no rule  (auto-approved)
    amount 500-4999          -> any_one  [building_manager]
    amount >= 5000           -> all_of_n [building_manager, property_owner]
    type=emergency           -> no rule  (auto-approved, no blackout)

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/maintenance-request-agent/agent.py
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
    user_id="auth0|maintenance_request_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

PROPERTIES = {
    "PROP-7001": {"address": "142 Oak Street, Apt 3B", "tenant": "John Rivera", "building": "Oak Terrace"},
    "PROP-7002": {"address": "88 Pine Ave, Unit 12", "tenant": "Lisa Chen", "building": "Pine Gardens"},
    "PROP-7003": {"address": "300 Elm Blvd, Suite 5A", "tenant": "TechStart Inc.", "building": "Elm Business Park"},
    "PROP-7004": {"address": "142 Oak Street, Apt 1A", "tenant": "Maria Santos", "building": "Oak Terrace"},
}

WORK_ORDERS = {
    "WO-001": {"property": "PROP-7001", "description": "Leaky kitchen faucet", "estimated_cost_usd": 150, "type": "small_repair"},
    "WO-002": {"property": "PROP-7002", "description": "HVAC compressor replacement", "estimated_cost_usd": 2800, "type": "medium_repair"},
    "WO-003": {"property": "PROP-7003", "description": "Full roof section repair", "estimated_cost_usd": 18500, "type": "large_repair"},
    "WO-004": {"property": "PROP-7004", "description": "Burst pipe flooding ground floor", "estimated_cost_usd": 4200, "type": "emergency"},
}

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="property-mgmt",
    action="maintenance",
    params_fn=lambda work_order_id: {
        "work_order_id": work_order_id,
        "property": PROPERTIES[WORK_ORDERS[work_order_id]["property"]]["address"],
        "tenant": PROPERTIES[WORK_ORDERS[work_order_id]["property"]]["tenant"],
        "description": WORK_ORDERS[work_order_id]["description"],
        "estimated_cost_usd": WORK_ORDERS[work_order_id]["estimated_cost_usd"],
        "type": "small_repair",
    },
)
def process_small_repair(work_order_id: str) -> dict:
    """
    Process a small repair (< $500).
    Auto-approved -- within pre-authorized maintenance budget.
    """
    wo = WORK_ORDERS[work_order_id]
    prop = PROPERTIES[wo["property"]]
    return {
        "work_order": work_order_id,
        "address": prop["address"],
        "description": wo["description"],
        "cost_usd": wo["estimated_cost_usd"],
        "status": "dispatched",
    }


@kit.requires_approval(
    connection="property-mgmt",
    action="maintenance",
    params_fn=lambda work_order_id: {
        "work_order_id": work_order_id,
        "property": PROPERTIES[WORK_ORDERS[work_order_id]["property"]]["address"],
        "building": PROPERTIES[WORK_ORDERS[work_order_id]["property"]]["building"],
        "tenant": PROPERTIES[WORK_ORDERS[work_order_id]["property"]]["tenant"],
        "description": WORK_ORDERS[work_order_id]["description"],
        "estimated_cost_usd": WORK_ORDERS[work_order_id]["estimated_cost_usd"],
        "type": "medium_repair",
    },
)
def process_medium_repair(work_order_id: str) -> dict:
    """
    Process a medium repair ($500 - $5,000).
    Requires building_manager approval.
    """
    wo = WORK_ORDERS[work_order_id]
    prop = PROPERTIES[wo["property"]]
    return {
        "work_order": work_order_id,
        "address": prop["address"],
        "description": wo["description"],
        "cost_usd": wo["estimated_cost_usd"],
        "status": "approved_and_dispatched",
    }


@kit.requires_approval(
    connection="property-mgmt",
    action="maintenance",
    params_fn=lambda work_order_id: {
        "work_order_id": work_order_id,
        "property": PROPERTIES[WORK_ORDERS[work_order_id]["property"]]["address"],
        "building": PROPERTIES[WORK_ORDERS[work_order_id]["property"]]["building"],
        "tenant": PROPERTIES[WORK_ORDERS[work_order_id]["property"]]["tenant"],
        "description": WORK_ORDERS[work_order_id]["description"],
        "estimated_cost_usd": WORK_ORDERS[work_order_id]["estimated_cost_usd"],
        "type": "large_repair",
    },
)
def process_large_repair(work_order_id: str) -> dict:
    """
    Process a large repair (>= $5,000).
    Requires both building_manager AND property_owner approval (all_of_n).
    """
    wo = WORK_ORDERS[work_order_id]
    prop = PROPERTIES[wo["property"]]
    return {
        "work_order": work_order_id,
        "address": prop["address"],
        "description": wo["description"],
        "cost_usd": wo["estimated_cost_usd"],
        "status": "approved_by_all",
    }


@kit.requires_approval(
    connection="property-mgmt",
    action="maintenance",
    params_fn=lambda work_order_id: {
        "work_order_id": work_order_id,
        "property": PROPERTIES[WORK_ORDERS[work_order_id]["property"]]["address"],
        "building": PROPERTIES[WORK_ORDERS[work_order_id]["property"]]["building"],
        "tenant": PROPERTIES[WORK_ORDERS[work_order_id]["property"]]["tenant"],
        "description": WORK_ORDERS[work_order_id]["description"],
        "estimated_cost_usd": WORK_ORDERS[work_order_id]["estimated_cost_usd"],
        "type": "emergency",
        "no_blackout": True,
    },
)
def process_emergency(work_order_id: str) -> dict:
    """
    Process an emergency maintenance request.
    Auto-approved with no blackout window -- immediate dispatch.
    """
    wo = WORK_ORDERS[work_order_id]
    prop = PROPERTIES[wo["property"]]
    return {
        "work_order": work_order_id,
        "address": prop["address"],
        "description": wo["description"],
        "cost_usd": wo["estimated_cost_usd"],
        "status": "emergency_dispatched",
    }


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Maintenance Request Agent Demo")
    print("="*60)

    # -- Scenario 1: Small repair -- auto-approved ---
    scenario("Scenario 1: Small repair ($150) -- auto-approved")
    try:
        result = process_small_repair("WO-001")
        print(f"  Dispatched: {result['description']}")
        print(f"  Address: {result['address']}")
        print(f"  Cost: ${result['cost_usd']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 2: Medium repair -- building_manager ---
    scenario("Scenario 2: Medium repair ($2,800) -- building_manager approval")
    try:
        result = process_medium_repair("WO-002")
        print(f"  Approved: {result['description']}")
        print(f"  Address: {result['address']}")
        print(f"  Cost: ${result['cost_usd']:,}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 3: Large repair -- building_manager + property_owner ---
    scenario("Scenario 3: Large repair ($18,500) -- building_manager + property_owner")
    print("  Both building_manager and property_owner must approve.")
    try:
        result = process_large_repair("WO-003")
        print(f"  Approved: {result['description']}")
        print(f"  Address: {result['address']}")
        print(f"  Cost: ${result['cost_usd']:,}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 4: Emergency -- auto-approved, no blackout ---
    scenario("Scenario 4: Emergency ($4,200) -- auto-approved, no blackout")
    print("  Burst pipe -- immediate dispatch regardless of time.")
    try:
        result = process_emergency("WO-004")
        print(f"  Emergency dispatched: {result['description']}")
        print(f"  Address: {result['address']}")
        print(f"  Cost: ${result['cost_usd']:,}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

"""
Demo Agent — Contract Signing (Legal)
======================================
Simulates an AI legal agent that handles NDAs, service agreements,
and partnership contracts with escalating approval requirements.

Rule configuration:

  docusign-prod : contract
    type=nda                -> no rule  (auto-approved)
    type=service_agreement  -> any_one  [legal]
    type=partnership        -> all_of_n [CEO, legal]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/contract-signing-agent/agent.py
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
    user_id="auth0|contract_signing_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

CONTRACTS = {
    "CTR-4001": {
        "counterparty": "Freelancer Inc.",
        "type": "nda",
        "value_usd": 0,
        "duration_months": 24,
        "description": "Standard mutual NDA for project consultation",
    },
    "CTR-4002": {
        "counterparty": "CloudOps Ltd.",
        "type": "service_agreement",
        "value_usd": 75000,
        "duration_months": 12,
        "description": "Annual infrastructure services agreement",
    },
    "CTR-4003": {
        "counterparty": "GlobalTech Partners",
        "type": "partnership",
        "value_usd": 2500000,
        "duration_months": 60,
        "description": "Strategic partnership for joint product development",
    },
}

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="docusign-prod",
    action="contract",
    params_fn=lambda contract_id: {
        "contract_id": contract_id,
        "counterparty": CONTRACTS[contract_id]["counterparty"],
        "type": "nda",
        "duration_months": CONTRACTS[contract_id]["duration_months"],
        "description": CONTRACTS[contract_id]["description"],
    },
)
def execute_nda(contract_id: str) -> dict:
    """
    Execute a standard NDA.
    Auto-approved -- uses pre-vetted template.
    """
    contract = CONTRACTS[contract_id]
    return {
        "contract_id": contract_id,
        "counterparty": contract["counterparty"],
        "type": "nda",
        "status": "executed",
    }


@kit.requires_approval(
    connection="docusign-prod",
    action="contract",
    params_fn=lambda contract_id: {
        "contract_id": contract_id,
        "counterparty": CONTRACTS[contract_id]["counterparty"],
        "type": "service_agreement",
        "value_usd": CONTRACTS[contract_id]["value_usd"],
        "duration_months": CONTRACTS[contract_id]["duration_months"],
        "description": CONTRACTS[contract_id]["description"],
    },
)
def execute_service_agreement(contract_id: str) -> dict:
    """
    Execute a service agreement.
    Requires legal team approval.
    """
    contract = CONTRACTS[contract_id]
    return {
        "contract_id": contract_id,
        "counterparty": contract["counterparty"],
        "value_usd": contract["value_usd"],
        "status": "executed",
    }


@kit.requires_approval(
    connection="docusign-prod",
    action="contract",
    params_fn=lambda contract_id: {
        "contract_id": contract_id,
        "counterparty": CONTRACTS[contract_id]["counterparty"],
        "type": "partnership",
        "value_usd": CONTRACTS[contract_id]["value_usd"],
        "duration_months": CONTRACTS[contract_id]["duration_months"],
        "description": CONTRACTS[contract_id]["description"],
    },
)
def execute_partnership(contract_id: str) -> dict:
    """
    Execute a partnership agreement.
    Requires both CEO AND legal approval (all_of_n).
    """
    contract = CONTRACTS[contract_id]
    return {
        "contract_id": contract_id,
        "counterparty": contract["counterparty"],
        "value_usd": contract["value_usd"],
        "status": "partnership_executed",
    }


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Contract Signing Agent Demo")
    print("="*60)

    # -- Scenario 1: NDA -- auto-approved ---
    scenario("Scenario 1: NDA -- auto-approved")
    try:
        result = execute_nda("CTR-4001")
        print(f"  NDA executed with {result['counterparty']}")
        print(f"  Status: {result['status']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 2: Service agreement -- legal approves ---
    scenario("Scenario 2: Service agreement ($75k) -- waiting for legal")
    try:
        result = execute_service_agreement("CTR-4002")
        print(f"  Agreement executed with {result['counterparty']}")
        print(f"  Value: ${result['value_usd']:,}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 3: Partnership -- CEO + legal ---
    scenario("Scenario 3: Partnership ($2.5M) -- CEO + legal required")
    print("  Both CEO and legal must approve.")
    try:
        result = execute_partnership("CTR-4003")
        print(f"  Partnership executed with {result['counterparty']}")
        print(f"  Value: ${result['value_usd']:,}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

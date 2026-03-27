"""
Demo Agent — Research Grant (Education)
=======================================
Simulates an AI agent that processes research grant applications
at a university with tiered approval based on amount.

Rule configuration:

  grants-portal : research_grant
    amount < 5000          -> any_one  [dept_head]
    amount 5000-49999      -> any_one  [rector]
    amount >= 50000        -> sequential [rector, external_reviewer]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/research-grant-agent/agent.py
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
    user_id="auth0|research_grant_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

RESEARCHERS = {
    "RES-3001": {"name": "Dr. James Liu", "department": "Chemistry", "title": "Associate Professor"},
    "RES-3002": {"name": "Dr. Sarah Okafor", "department": "Engineering", "title": "Professor"},
    "RES-3003": {"name": "Dr. Michael Petrov", "department": "Physics", "title": "Distinguished Professor"},
}

PROPOSALS = {
    "PROP-001": {
        "researcher": "RES-3001",
        "title": "Catalyst efficiency in organic solvents",
        "amount_usd": 3500,
        "duration_months": 6,
    },
    "PROP-002": {
        "researcher": "RES-3002",
        "title": "AI-driven bridge stress analysis",
        "amount_usd": 25000,
        "duration_months": 12,
    },
    "PROP-003": {
        "researcher": "RES-3003",
        "title": "Quantum entanglement applications in computing",
        "amount_usd": 120000,
        "duration_months": 36,
    },
}

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="grants-portal",
    action="research_grant",
    params_fn=lambda proposal_id: {
        "proposal_id": proposal_id,
        "researcher": RESEARCHERS[PROPOSALS[proposal_id]["researcher"]]["name"],
        "department": RESEARCHERS[PROPOSALS[proposal_id]["researcher"]]["department"],
        "title": PROPOSALS[proposal_id]["title"],
        "amount_usd": PROPOSALS[proposal_id]["amount_usd"],
        "duration_months": PROPOSALS[proposal_id]["duration_months"],
        "tier": "small_grant",
    },
)
def approve_small_grant(proposal_id: str) -> dict:
    """
    Approve a small research grant (< $5,000).
    Requires dept_head approval.
    """
    proposal = PROPOSALS[proposal_id]
    researcher = RESEARCHERS[proposal["researcher"]]
    return {
        "researcher": researcher["name"],
        "title": proposal["title"],
        "amount_usd": proposal["amount_usd"],
        "status": "small_grant_approved",
    }


@kit.requires_approval(
    connection="grants-portal",
    action="research_grant",
    params_fn=lambda proposal_id: {
        "proposal_id": proposal_id,
        "researcher": RESEARCHERS[PROPOSALS[proposal_id]["researcher"]]["name"],
        "department": RESEARCHERS[PROPOSALS[proposal_id]["researcher"]]["department"],
        "title": PROPOSALS[proposal_id]["title"],
        "amount_usd": PROPOSALS[proposal_id]["amount_usd"],
        "duration_months": PROPOSALS[proposal_id]["duration_months"],
        "tier": "medium_grant",
    },
)
def approve_medium_grant(proposal_id: str) -> dict:
    """
    Approve a medium research grant ($5,000 - $49,999).
    Requires rector approval.
    """
    proposal = PROPOSALS[proposal_id]
    researcher = RESEARCHERS[proposal["researcher"]]
    return {
        "researcher": researcher["name"],
        "title": proposal["title"],
        "amount_usd": proposal["amount_usd"],
        "status": "medium_grant_approved",
    }


@kit.requires_approval(
    connection="grants-portal",
    action="research_grant",
    params_fn=lambda proposal_id: {
        "proposal_id": proposal_id,
        "researcher": RESEARCHERS[PROPOSALS[proposal_id]["researcher"]]["name"],
        "department": RESEARCHERS[PROPOSALS[proposal_id]["researcher"]]["department"],
        "title_of_research": PROPOSALS[proposal_id]["title"],
        "amount_usd": PROPOSALS[proposal_id]["amount_usd"],
        "duration_months": PROPOSALS[proposal_id]["duration_months"],
        "tier": "large_grant",
    },
)
def approve_large_grant(proposal_id: str) -> dict:
    """
    Approve a large research grant (>= $50,000).
    Requires rector THEN external_reviewer (sequential approval).
    """
    proposal = PROPOSALS[proposal_id]
    researcher = RESEARCHERS[proposal["researcher"]]
    return {
        "researcher": researcher["name"],
        "title": proposal["title"],
        "amount_usd": proposal["amount_usd"],
        "status": "large_grant_approved",
    }


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Research Grant Agent Demo")
    print("="*60)

    # -- Scenario 1: Small grant -- dept_head ---
    scenario("Scenario 1: Small grant ($3,500) -- dept_head approval")
    try:
        result = approve_small_grant("PROP-001")
        print(f"  Approved: {result['researcher']}")
        print(f"  Project: {result['title']}")
        print(f"  Amount: ${result['amount_usd']:,}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 2: Medium grant -- rector ---
    scenario("Scenario 2: Medium grant ($25,000) -- rector approval")
    try:
        result = approve_medium_grant("PROP-002")
        print(f"  Approved: {result['researcher']}")
        print(f"  Project: {result['title']}")
        print(f"  Amount: ${result['amount_usd']:,}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 3: Large grant -- rector then external reviewer ---
    scenario("Scenario 3: Large grant ($120,000) -- rector + external (sequential)")
    print("  Rector must approve first, then external reviewer.")
    try:
        result = approve_large_grant("PROP-003")
        print(f"  Approved: {result['researcher']}")
        print(f"  Project: {result['title']}")
        print(f"  Amount: ${result['amount_usd']:,}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

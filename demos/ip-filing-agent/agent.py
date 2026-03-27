"""
Demo Agent — IP Filing (Legal)
===============================
Simulates an AI agent that manages intellectual property filings
including drafts, domestic filings, and international filings.

Rule configuration:

  ip-portal : ip_filing
    type=draft                -> no rule  (auto-approved)
    type=domestic_filing      -> any_one  [legal]
    type=international_filing -> all_of_n [CEO, legal]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/ip-filing-agent/agent.py
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
    user_id="auth0|ip_filing_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

INVENTIONS = {
    "INV-6001": {
        "title": "Adaptive noise-cancellation algorithm",
        "inventor": "Dr. Yuki Tanaka",
        "department": "R&D Audio",
        "filing_cost_usd": 0,
    },
    "INV-6002": {
        "title": "Low-power wireless sensor mesh protocol",
        "inventor": "Dr. Ahmed Hassan",
        "department": "IoT Division",
        "filing_cost_usd": 8500,
    },
    "INV-6003": {
        "title": "Quantum-resistant encryption method",
        "inventor": "Dr. Elena Volkov",
        "department": "Security Research",
        "filing_cost_usd": 65000,
    },
}

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="ip-portal",
    action="ip_filing",
    params_fn=lambda invention_id: {
        "invention_id": invention_id,
        "title": INVENTIONS[invention_id]["title"],
        "inventor": INVENTIONS[invention_id]["inventor"],
        "department": INVENTIONS[invention_id]["department"],
        "type": "draft",
    },
)
def create_draft(invention_id: str) -> dict:
    """
    Create a patent application draft.
    Auto-approved -- internal preparation step.
    """
    invention = INVENTIONS[invention_id]
    return {
        "invention_id": invention_id,
        "title": invention["title"],
        "inventor": invention["inventor"],
        "status": "draft_created",
    }


@kit.requires_approval(
    connection="ip-portal",
    action="ip_filing",
    params_fn=lambda invention_id: {
        "invention_id": invention_id,
        "title": INVENTIONS[invention_id]["title"],
        "inventor": INVENTIONS[invention_id]["inventor"],
        "department": INVENTIONS[invention_id]["department"],
        "filing_cost_usd": INVENTIONS[invention_id]["filing_cost_usd"],
        "type": "domestic_filing",
        "jurisdiction": "US-USPTO",
    },
)
def file_domestic_patent(invention_id: str) -> dict:
    """
    File a domestic patent application with USPTO.
    Requires legal team approval.
    """
    invention = INVENTIONS[invention_id]
    return {
        "invention_id": invention_id,
        "title": invention["title"],
        "filing_cost_usd": invention["filing_cost_usd"],
        "jurisdiction": "US-USPTO",
        "status": "domestic_filed",
    }


@kit.requires_approval(
    connection="ip-portal",
    action="ip_filing",
    params_fn=lambda invention_id, jurisdictions: {
        "invention_id": invention_id,
        "title": INVENTIONS[invention_id]["title"],
        "inventor": INVENTIONS[invention_id]["inventor"],
        "department": INVENTIONS[invention_id]["department"],
        "filing_cost_usd": INVENTIONS[invention_id]["filing_cost_usd"],
        "type": "international_filing",
        "jurisdictions": jurisdictions,
    },
)
def file_international_patent(invention_id: str, jurisdictions: list) -> dict:
    """
    File an international patent (PCT / multi-jurisdiction).
    Requires both CEO AND legal approval (all_of_n).
    """
    invention = INVENTIONS[invention_id]
    return {
        "invention_id": invention_id,
        "title": invention["title"],
        "filing_cost_usd": invention["filing_cost_usd"],
        "jurisdictions": jurisdictions,
        "status": "international_filed",
    }


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  IP Filing Agent Demo")
    print("="*60)

    # -- Scenario 1: Draft -- auto-approved ---
    scenario("Scenario 1: Create patent draft -- auto-approved")
    try:
        result = create_draft("INV-6001")
        print(f"  Draft created: {result['title']}")
        print(f"  Inventor: {result['inventor']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 2: Domestic filing -- legal ---
    scenario("Scenario 2: Domestic USPTO filing ($8,500) -- legal approval")
    try:
        result = file_domestic_patent("INV-6002")
        print(f"  Filed: {result['title']}")
        print(f"  Cost: ${result['filing_cost_usd']:,}")
        print(f"  Jurisdiction: {result['jurisdiction']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 3: International filing -- CEO + legal ---
    scenario("Scenario 3: International filing ($65,000) -- CEO + legal")
    print("  Both CEO and legal must approve.")
    try:
        result = file_international_patent(
            "INV-6003",
            ["US-USPTO", "EU-EPO", "JP-JPO", "CN-CNIPA"]
        )
        print(f"  Filed: {result['title']}")
        print(f"  Cost: ${result['filing_cost_usd']:,}")
        print(f"  Jurisdictions: {', '.join(result['jurisdictions'])}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

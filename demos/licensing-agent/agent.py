"""
Demo Agent — Licensing (Media)
===============================
Simulates an AI agent that manages content licensing deals
from personal use to major commercial agreements.

Rule configuration:

  licensing-portal : license
    type=personal        -> no rule  (auto-approved)
    type=commercial      -> any_one  [legal]
    amount >= 100000     -> all_of_n [CEO, legal]  (major_deal)

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/licensing-agent/agent.py
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
    user_id="auth0|licensing_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

ASSETS = {
    "ASSET-1001": {"title": "Sunset Over Mountains", "type": "photo", "creator": "Jane Doe Photography"},
    "ASSET-1002": {"title": "Corporate Intro Pack", "type": "music_library", "creator": "SoundWave Studios"},
    "ASSET-1003": {"title": "Blockbuster Film Score", "type": "soundtrack", "creator": "Epic Compositions Ltd."},
}

LICENSE_REQUESTS = {
    "LIC-001": {
        "asset": "ASSET-1001",
        "licensee": "john@personal.com",
        "license_type": "personal",
        "fee_usd": 0,
        "usage": "Personal blog post",
    },
    "LIC-002": {
        "asset": "ASSET-1002",
        "licensee": "marketing@startup.io",
        "license_type": "commercial",
        "fee_usd": 5000,
        "usage": "Product launch video campaign",
    },
    "LIC-003": {
        "asset": "ASSET-1003",
        "licensee": "licensing@majorcorp.com",
        "license_type": "major_deal",
        "fee_usd": 350000,
        "usage": "Global advertising campaign, 3-year exclusive",
    },
}

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="licensing-portal",
    action="license",
    params_fn=lambda license_id: {
        "license_id": license_id,
        "asset_title": ASSETS[LICENSE_REQUESTS[license_id]["asset"]]["title"],
        "licensee": LICENSE_REQUESTS[license_id]["licensee"],
        "usage": LICENSE_REQUESTS[license_id]["usage"],
        "type": "personal",
    },
)
def grant_personal_license(license_id: str) -> dict:
    """
    Grant a personal-use license.
    Auto-approved -- free non-commercial use.
    """
    req = LICENSE_REQUESTS[license_id]
    asset = ASSETS[req["asset"]]
    return {
        "license_id": license_id,
        "asset": asset["title"],
        "licensee": req["licensee"],
        "status": "personal_license_granted",
    }


@kit.requires_approval(
    connection="licensing-portal",
    action="license",
    params_fn=lambda license_id: {
        "license_id": license_id,
        "asset_title": ASSETS[LICENSE_REQUESTS[license_id]["asset"]]["title"],
        "creator": ASSETS[LICENSE_REQUESTS[license_id]["asset"]]["creator"],
        "licensee": LICENSE_REQUESTS[license_id]["licensee"],
        "fee_usd": LICENSE_REQUESTS[license_id]["fee_usd"],
        "usage": LICENSE_REQUESTS[license_id]["usage"],
        "type": "commercial",
    },
)
def grant_commercial_license(license_id: str) -> dict:
    """
    Grant a commercial license.
    Requires legal team approval.
    """
    req = LICENSE_REQUESTS[license_id]
    asset = ASSETS[req["asset"]]
    return {
        "license_id": license_id,
        "asset": asset["title"],
        "licensee": req["licensee"],
        "fee_usd": req["fee_usd"],
        "status": "commercial_license_granted",
    }


@kit.requires_approval(
    connection="licensing-portal",
    action="license",
    params_fn=lambda license_id: {
        "license_id": license_id,
        "asset_title": ASSETS[LICENSE_REQUESTS[license_id]["asset"]]["title"],
        "creator": ASSETS[LICENSE_REQUESTS[license_id]["asset"]]["creator"],
        "licensee": LICENSE_REQUESTS[license_id]["licensee"],
        "fee_usd": LICENSE_REQUESTS[license_id]["fee_usd"],
        "usage": LICENSE_REQUESTS[license_id]["usage"],
        "type": "major_deal",
    },
)
def grant_major_deal(license_id: str) -> dict:
    """
    Grant a major licensing deal (>= $100,000).
    Requires both CEO AND legal approval (all_of_n).
    """
    req = LICENSE_REQUESTS[license_id]
    asset = ASSETS[req["asset"]]
    return {
        "license_id": license_id,
        "asset": asset["title"],
        "licensee": req["licensee"],
        "fee_usd": req["fee_usd"],
        "status": "major_deal_executed",
    }


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Licensing Agent Demo")
    print("="*60)

    # -- Scenario 1: Personal license -- auto-approved ---
    scenario("Scenario 1: Personal license (free) -- auto-approved")
    try:
        result = grant_personal_license("LIC-001")
        print(f"  Granted: {result['asset']}")
        print(f"  Licensee: {result['licensee']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 2: Commercial license -- legal ---
    scenario("Scenario 2: Commercial license ($5,000) -- legal approval")
    try:
        result = grant_commercial_license("LIC-002")
        print(f"  Granted: {result['asset']}")
        print(f"  Fee: ${result['fee_usd']:,}")
        print(f"  Licensee: {result['licensee']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 3: Major deal -- CEO + legal ---
    scenario("Scenario 3: Major deal ($350,000) -- CEO + legal required")
    print("  Both CEO and legal must approve.")
    try:
        result = grant_major_deal("LIC-003")
        print(f"  Executed: {result['asset']}")
        print(f"  Fee: ${result['fee_usd']:,}")
        print(f"  Licensee: {result['licensee']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

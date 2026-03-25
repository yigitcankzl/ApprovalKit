"""
Demo Agent — Financial Services
=================================
Simulates a fintech payment agent with a strict compliance chain.
Transfers escalate through operations, finance, and CFO depending
on amount. New vendors require procurement + legal. Wire transfers
go through a full sequential chain.

Rules:
  stripe-prod : payout
    amount <= 10000      → any_one [manager]
    amount > 10000       → sequential [manager → compliance → cfo]

  stripe-prod : vendor_payment
    (new vendor)         → all_of_n [procurement, legal]

  stripe-prod : wire_transfer
    (any)                → sequential [ops → finance → cfo]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/fintech_agent.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk"))
from approvalkit import ApprovalKit, ApprovalDenied

kit = ApprovalKit(
    base_url=os.environ.get("APPROVALKIT_URL", "http://localhost:8000"),
    api_key=os.environ.get("APPROVALKIT_API_KEY", ""),
    hmac_secret=os.environ.get("APPROVALKIT_HMAC_SECRET", ""),
    user_id="auth0|fintech_agent",
    poll_interval=3,
    timeout=180,
)

# ── Actions ───────────────────────────────────────────────────────────────────

@kit.requires_approval(
    connection="stripe-prod",
    action="payout",
    params_fn=lambda amount, recipient, reference: {
        "amount_usd": amount,
        "recipient": recipient,
        "reference": reference,
    },
)
def send_payout(amount: float, recipient: str, reference: str) -> dict:
    """Send a payout. High-value payouts require sequential approval chain."""
    return {"paid": amount, "to": recipient, "ref": reference}


@kit.requires_approval(
    connection="stripe-prod",
    action="vendor_payment",
    params_fn=lambda vendor_name, amount, is_new_vendor, invoice_id: {
        "vendor_name": vendor_name,
        "amount_usd": amount,
        "is_new_vendor": is_new_vendor,
        "invoice_id": invoice_id,
    },
)
def pay_vendor(vendor_name: str, amount: float, is_new_vendor: bool, invoice_id: str) -> dict:
    """Pay a vendor. New vendors require procurement + legal sign-off."""
    return {"paid_to": vendor_name, "amount": amount}


@kit.requires_approval(
    connection="stripe-prod",
    action="wire_transfer",
    params_fn=lambda amount, beneficiary, iban, purpose: {
        "amount_usd": amount,
        "beneficiary": beneficiary,
        "iban": iban[:8] + "****",
        "purpose": purpose,
    },
)
def wire_transfer(amount: float, beneficiary: str, iban: str, purpose: str) -> dict:
    """Execute a wire transfer. Always requires ops → finance → CFO chain."""
    return {"wired": amount, "to": beneficiary}


# ── Scenarios ─────────────────────────────────────────────────────────────────

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Financial Services Agent Demo")
    print("="*60)

    scenario("Scenario 1: Standard payout $4,500 — manager approval")
    try:
        result = send_payout(4500.0, "supplier@example.com", "INV-2026-0441")
        print(f"  Payout complete: ${result['paid']} to {result['to']} ({result['ref']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    scenario("Scenario 2: Large payout $85,000 — sequential (manager → compliance → CFO)")
    print("  Three-step chain: each approver is notified in order.")
    try:
        result = send_payout(85000.0, "acquisition@example.com", "DEAL-2026-007")
        print(f"  Payout complete: ${result['paid']} to {result['to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    scenario("Scenario 3: New vendor payment — procurement + legal (all_of_n)")
    print("  New vendor onboarding requires dual compliance check.")
    try:
        result = pay_vendor("NewCloud GmbH", 12000.0, True, "INV-NC-001")
        print(f"  Paid ${result['amount']} to {result['paid_to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    scenario("Scenario 4: Wire transfer $250,000 — ops → finance → CFO (sequential)")
    print("  Full compliance chain for international wire.")
    try:
        result = wire_transfer(
            250000.0,
            "Acme Holdings Ltd",
            "GB29NWBK60161331926819",
            "Series B investment tranche"
        )
        print(f"  Wire complete: ${result['wired']} to {result['to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

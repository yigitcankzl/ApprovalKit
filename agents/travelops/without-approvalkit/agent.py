#!/usr/bin/env python3
"""
TravelOps Agent — WITHOUT ApprovalKit
======================================
This is the UNSAFE version. The agent has direct access to Stripe API keys,
executes charges without any human approval, and there's no audit trail.

Compare with the ApprovalKit version to see the difference:
  - Agent holds raw Stripe API key (credential exposure)
  - No human approval for any transaction
  - No step-up for high-value bookings
  - No audit log
  - No scope creep detection
  - If the agent hallucinates a wrong amount, money is gone

Usage:
    export STRIPE_API_KEY=sk_test_xxx
    python agent.py --dest berlin --flight-price 349 --hotel-price 95

This version exists purely for comparison. DO NOT use in production.
"""

import os
import sys
import json
import random
import string
from datetime import datetime

# In the unsafe version, the agent directly imports stripe
# and holds the API key in memory
try:
    import stripe
    stripe.api_key = os.getenv("STRIPE_API_KEY", "sk_test_FAKE_KEY_NOT_REAL")
    HAS_STRIPE = True
except ImportError:
    HAS_STRIPE = False

# ── Travel Data (same as ApprovalKit version) ─────────────────────────────────

FLIGHTS = {
    "berlin": [
        {"airline": "Lufthansa", "price": 420, "class": "economy", "duration": "2h 35m", "flight_no": "LH1834"},
        {"airline": "Lufthansa", "price": 1850, "class": "business", "duration": "2h 35m", "flight_no": "LH1834"},
    ],
    "london": [
        {"airline": "British Airways", "price": 350, "class": "economy", "duration": "3h 50m", "flight_no": "BA680"},
        {"airline": "British Airways", "price": 1400, "class": "business", "duration": "3h 50m", "flight_no": "BA680"},
    ],
    "new york": [
        {"airline": "Delta", "price": 890, "class": "economy", "duration": "10h 20m", "flight_no": "DL34"},
        {"airline": "Delta", "price": 3200, "class": "business", "duration": "10h 20m", "flight_no": "DL34"},
    ],
}

HOTELS = {
    "berlin": [{"name": "Motel One", "price": 120, "stars": 3}],
    "london": [{"name": "Premier Inn", "price": 110, "stars": 3}],
    "new york": [{"name": "Pod 51", "price": 130, "stars": 3}],
}


def _ref():
    return "TVL-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


# ── UNSAFE: Direct Stripe Charge ──────────────────────────────────────────────

def charge_stripe(amount: float, description: str, customer: str) -> dict:
    """
    UNSAFE: Agent directly charges Stripe.
    - Agent holds the API key
    - No human reviews the charge
    - No approval for high amounts
    - If amount is wrong, money is gone
    """
    api_key = os.getenv("STRIPE_API_KEY", "sk_test_FAKE_KEY_NOT_REAL")
    print(f"      [STRIPE] Charging ${amount} — {description}")
    print(f"      [STRIPE] API Key: {api_key[:20]}... (EXPOSED TO AGENT)")

    if not HAS_STRIPE or "FAKE" in api_key:
        print(f"      [STRIPE] (simulated — no real charge)")
        return {"id": f"pi_fake_{random.randint(1000,9999)}", "status": "succeeded", "amount": int(amount * 100)}

    # Real Stripe charge — no approval, no review
    intent = stripe.PaymentIntent.create(
        amount=int(amount * 100),
        currency="usd",
        description=description,
        payment_method_types=["card"],
    )
    return {"id": intent.id, "status": intent.status, "amount": intent.amount}


def send_email_direct(to: str, subject: str, body: str):
    """UNSAFE: No approval for emails either."""
    print(f"      [EMAIL] Sending to {to}: {subject}")
    print(f"      [EMAIL] (no approval — sent immediately)")


def post_slack_direct(channel: str, message: str):
    """UNSAFE: No approval for Slack messages."""
    print(f"      [SLACK] Posting to {channel}: {message[:50]}...")
    print(f"      [SLACK] (no approval — posted immediately)")


# ── Agent Logic ───────────────────────────────────────────────────────────────

def run_trip(traveler: str, destination: str, purpose: str, nights: int,
             flight_class: str = "economy", flight_price: float = None, hotel_price: float = None):

    dest = destination.lower()
    flights = FLIGHTS.get(dest, FLIGHTS["berlin"])
    hotels = HOTELS.get(dest, HOTELS["berlin"])
    flight = next((f for f in flights if f["class"] == flight_class), flights[0])
    hotel = hotels[0]
    price = flight_price or flight["price"]
    h_price = hotel_price or hotel["price"]
    hotel_total = h_price * nights
    ref = _ref()

    print(f"\n{'='*60}")
    print(f"  TravelOps Agent (NO APPROVALKIT)")
    print(f"  WARNING: No human approval — all actions execute immediately")
    print(f"{'='*60}")
    print(f"  Traveler: {traveler}")
    print(f"  Trip: {destination.title()} — {purpose}")
    print(f"  Ref: {ref}")
    print(f"{'='*60}")

    total = 0

    # 1. Flight — NO APPROVAL
    print(f"\n[1/7] Flight: {flight['airline']} {flight['flight_no']} ({flight['class']}) — ${price}")
    print(f"      NO APPROVAL NEEDED — charging immediately")
    charge_stripe(price, f"Flight {flight['flight_no']} to {destination}", traveler)
    total += price
    print(f"      Charged. No one reviewed this.")

    # 2. Hotel — NO APPROVAL
    print(f"\n[2/7] Hotel: {hotel['name']} — ${h_price}/night x {nights} = ${hotel_total}")
    print(f"      NO APPROVAL NEEDED — charging immediately")
    charge_stripe(hotel_total, f"Hotel {hotel['name']} {nights}n", traveler)
    total += hotel_total
    print(f"      Charged. No one reviewed this.")

    # 3. Insurance — NO APPROVAL
    print(f"\n[3/7] Insurance: Basic Travel Cover — $29")
    charge_stripe(29, "Travel insurance", traveler)
    total += 29
    print(f"      Charged.")

    # 4. Calendar
    print(f"\n[4/7] Calendar: Added '{purpose}' (no approval needed)")

    # 5. Slack — NO APPROVAL
    print(f"\n[5/7] Slack: Posting to #travel")
    post_slack_direct("#travel", f"{traveler} traveling to {destination} for {purpose}")

    # 6. Expense
    print(f"\n[6/7] Expense: ${total} logged")

    # 7. Visa
    needs_visa = dest in ("new york", "san francisco", "tokyo")
    if needs_visa:
        print(f"\n[7/7] Visa: Required — sending reminder")
        send_email_direct(traveler, f"Visa reminder: {destination}", "Apply for visa ASAP")
    else:
        print(f"\n[7/7] Visa: Not required")

    print(f"\n{'='*60}")
    print(f"  UNSAFE SUMMARY — {ref}")
    print(f"{'='*60}")
    print(f"  Total charged: ${total}")
    print(f"  Human approvals: 0")
    print(f"  Audit trail: NONE")
    print(f"  Credential exposure: Stripe API key held by agent")
    print(f"")
    print(f"  RISKS:")
    print(f"  - Agent charged ${price} flight without anyone reviewing")
    if price > 2000:
        print(f"  - HIGH VALUE: ${price} charge had NO step-up authentication")
    print(f"  - Agent could charge ANY amount — no guardrails")
    print(f"  - If agent hallucinates wrong amount, money is lost")
    print(f"  - No way to revoke agent's access to Stripe")
    print(f"  - Stripe API key exposed in agent memory")
    print(f"{'='*60}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TravelOps Agent (UNSAFE — no ApprovalKit)")
    parser.add_argument("--traveler", default="alice@company.com")
    parser.add_argument("--dest", default="berlin")
    parser.add_argument("--purpose", default="React Conf 2026")
    parser.add_argument("--nights", type=int, default=3)
    parser.add_argument("--class", dest="flight_class", default="economy")
    parser.add_argument("--flight-price", type=float, default=None)
    parser.add_argument("--hotel-price", type=float, default=None)
    args = parser.parse_args()

    run_trip(
        traveler=args.traveler,
        destination=args.dest,
        purpose=args.purpose,
        nights=args.nights,
        flight_class=args.flight_class,
        flight_price=args.flight_price,
        hotel_price=args.hotel_price,
    )

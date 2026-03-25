#!/usr/bin/env python3
"""
TravelOps Agent — Corporate Travel Manager
============================================
Manages end-to-end business travel: flights, hotels, insurance,
calendar, team notifications, expense reporting, and visa reminders.

Every action goes through ApprovalKit — amount-based step-up ensures
cheap flights auto-approve while expensive ones need CFO sign-off.

Usage:
    python agent.py "Berlin conference next Monday, 3 nights"
    python agent.py --flight 1200 --hotel 180 --dest Berlin --purpose "React Conf 2026"

Env vars:
    APPROVALKIT_URL          http://localhost:8000
    APPROVALKIT_API_KEY      (from workspace setup)
    APPROVALKIT_HMAC_SECRET  (from workspace setup)
"""

import os
import sys
import json
import random
import string
from datetime import datetime, timedelta

# Add parent dirs so we can import the SDK
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "examples"))

from approvalkit_sdk import ApprovalKit, ApprovalDenied

# ── Config ────────────────────────────────────────────────────────────────────

kit = ApprovalKit(
    base_url=os.getenv("APPROVALKIT_URL", "http://localhost:8000"),
    api_key=os.getenv("APPROVALKIT_API_KEY", ""),
    hmac_secret=os.getenv("APPROVALKIT_HMAC_SECRET", ""),
    user_id="travelops-agent",
)

# ── Travel Data (simulated search results) ────────────────────────────────────

FLIGHTS = {
    "berlin": [
        {"airline": "Lufthansa", "price": 420, "class": "economy", "duration": "2h 35m", "departure": "08:30", "flight_no": "LH1834"},
        {"airline": "Turkish Airlines", "price": 680, "class": "economy", "duration": "3h 45m", "departure": "11:15", "flight_no": "TK1721"},
        {"airline": "Lufthansa", "price": 1850, "class": "business", "duration": "2h 35m", "departure": "08:30", "flight_no": "LH1834"},
        {"airline": "Private Charter", "price": 4500, "class": "first", "duration": "2h 10m", "departure": "flexible", "flight_no": "PVT001"},
    ],
    "london": [
        {"airline": "British Airways", "price": 350, "class": "economy", "duration": "3h 50m", "departure": "07:00", "flight_no": "BA680"},
        {"airline": "British Airways", "price": 1400, "class": "business", "duration": "3h 50m", "departure": "07:00", "flight_no": "BA680"},
    ],
    "new york": [
        {"airline": "Delta", "price": 890, "class": "economy", "duration": "10h 20m", "departure": "22:00", "flight_no": "DL34"},
        {"airline": "Delta", "price": 3200, "class": "business", "duration": "10h 20m", "departure": "22:00", "flight_no": "DL34"},
    ],
    "san francisco": [
        {"airline": "United", "price": 950, "class": "economy", "duration": "13h 15m", "departure": "16:30", "flight_no": "UA90"},
        {"airline": "United", "price": 3800, "class": "business", "duration": "13h 15m", "departure": "16:30", "flight_no": "UA90"},
    ],
}

HOTELS = {
    "berlin": [
        {"name": "Holiday Inn Berlin Centre", "price_per_night": 95, "stars": 3, "rating": 4.1},
        {"name": "Motel One Berlin-Alexanderplatz", "price_per_night": 120, "stars": 3, "rating": 4.3},
        {"name": "Hotel Adlon Kempinski", "price_per_night": 380, "stars": 5, "rating": 4.8},
    ],
    "london": [
        {"name": "Premier Inn London City", "price_per_night": 110, "stars": 3, "rating": 4.0},
        {"name": "The Savoy", "price_per_night": 520, "stars": 5, "rating": 4.9},
    ],
    "new york": [
        {"name": "Pod 51 Hotel", "price_per_night": 130, "stars": 3, "rating": 4.0},
        {"name": "The Plaza", "price_per_night": 650, "stars": 5, "rating": 4.7},
    ],
    "san francisco": [
        {"name": "HI San Francisco Downtown", "price_per_night": 85, "stars": 2, "rating": 3.8},
        {"name": "The Ritz-Carlton", "price_per_night": 490, "stars": 5, "rating": 4.8},
    ],
}

INSURANCE_PLANS = [
    {"name": "Basic Travel Cover", "price": 29, "coverage": "$50,000"},
    {"name": "Premium Travel Cover", "price": 59, "coverage": "$200,000"},
    {"name": "Executive Travel Cover", "price": 119, "coverage": "$500,000"},
]

VISA_REQUIRED = {
    "berlin": False, "london": False, "new york": True,
    "san francisco": True, "tokyo": True, "dubai": True,
}


def _ref():
    return "TVL-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


# ── Approval-gated actions ────────────────────────────────────────────────────

@kit.requires_approval(
    connection="stripe-prod",
    action="charge",
    params_fn=lambda price, desc, ref, traveler: {
        "amount_usd": price,
        "description": desc,
        "reference": ref,
        "customer": traveler,
    },
)
def book_flight(price: float, desc: str, ref: str, traveler: str):
    """Book flight — Token Vault charges via Stripe."""
    pass


@kit.requires_approval(
    connection="stripe-prod",
    action="charge",
    params_fn=lambda total, desc, ref, traveler: {
        "amount_usd": total,
        "description": desc,
        "reference": ref,
        "customer": traveler,
    },
)
def book_hotel(total: float, desc: str, ref: str, traveler: str):
    """Book hotel — Token Vault charges via Stripe."""
    pass


@kit.requires_approval(
    connection="stripe-prod",
    action="charge",
    params_fn=lambda price, plan_name, ref, traveler: {
        "amount_usd": price,
        "description": f"Travel insurance: {plan_name}",
        "reference": ref,
        "customer": traveler,
    },
)
def buy_insurance(price: float, plan_name: str, ref: str, traveler: str):
    """Buy travel insurance — Token Vault charges via Stripe."""
    pass


@kit.requires_approval(
    connection="slack-prod",
    action="send_message",
    params_fn=lambda channel, message: {
        "channel": channel,
        "message": message,
    },
)
def notify_team(channel: str, message: str):
    """Post travel notification to Slack."""
    pass


@kit.requires_approval(
    connection="gmail-prod",
    action="send_email",
    params_fn=lambda recipient, subject, body, email_type: {
        "recipient": recipient,
        "subject": subject,
        "body": body,
        "type": email_type,
    },
)
def send_email(recipient: str, subject: str, body: str, email_type: str = "notification"):
    """Send email via Gmail — Token Vault executes."""
    pass


# ── Agent Logic ───────────────────────────────────────────────────────────────

class TravelOpsAgent:
    def __init__(self, traveler: str, destination: str, purpose: str, nights: int = 2):
        self.traveler = traveler
        self.destination = destination.lower()
        self.purpose = purpose
        self.nights = nights
        self.trip_ref = _ref()
        self.results = {}
        self.total_cost = 0

    def search_flights(self) -> list[dict]:
        flights = FLIGHTS.get(self.destination, FLIGHTS["berlin"])
        return flights

    def search_hotels(self) -> list[dict]:
        hotels = HOTELS.get(self.destination, HOTELS["berlin"])
        return hotels

    def recommend_flight(self, budget: str = "economy") -> dict:
        flights = self.search_flights()
        if budget == "business":
            return next((f for f in flights if f["class"] == "business"), flights[-1])
        return flights[0]  # cheapest economy

    def recommend_hotel(self) -> dict:
        hotels = self.search_hotels()
        # Pick mid-range
        return hotels[len(hotels) // 2] if len(hotels) > 1 else hotels[0]

    def recommend_insurance(self) -> dict:
        return INSURANCE_PLANS[0]  # Basic

    def needs_visa(self) -> bool:
        return VISA_REQUIRED.get(self.destination, False)

    def run(self, flight_class: str = "economy", override_flight_price: float | None = None, override_hotel_price: float | None = None):
        dest_title = self.destination.title()
        print(f"\n{'='*60}")
        print(f"  TravelOps Agent  |  {self.traveler}")
        print(f"  Trip: {dest_title} — {self.purpose}")
        print(f"  Ref: {self.trip_ref}")
        print(f"{'='*60}")

        # ── Step 1: Flight ────────────────────────────────────────────
        flight = self.recommend_flight(flight_class)
        price = override_flight_price or flight["price"]
        print(f"\n[1/7] Flight: {flight['airline']} {flight['flight_no']} ({flight['class']}) — ${price}")
        print(f"      {flight['departure']} departure, {flight['duration']}")

        try:
            result = book_flight(
                price,
                f"Flight {flight['flight_no']} to {dest_title} ({flight['class']})",
                self.trip_ref,
                self.traveler,
            )
            self.results["flight"] = {"status": "booked", "price": price, **flight}
            self.total_cost += price
            print(f"      Approved — flight booked.")
        except ApprovalDenied as e:
            print(f"      DENIED — {e.status}. Trip cancelled.")
            self.results["flight"] = {"status": "denied"}
            return self.results

        # ── Step 2: Hotel ─────────────────────────────────────────────
        hotel = self.recommend_hotel()
        night_price = override_hotel_price or hotel["price_per_night"]
        total_hotel = night_price * self.nights
        print(f"\n[2/7] Hotel: {hotel['name']} — ${night_price}/night x {self.nights} = ${total_hotel}")

        try:
            result = book_hotel(
                total_hotel,
                f"Hotel {hotel['name']} {self.nights}n in {dest_title}",
                self.trip_ref,
                self.traveler,
            )
            self.results["hotel"] = {"status": "booked", "total": total_hotel, **hotel}
            self.total_cost += total_hotel
            print(f"      Approved — hotel reserved.")
        except ApprovalDenied as e:
            print(f"      DENIED — {e.status}. Continuing without hotel.")
            self.results["hotel"] = {"status": "denied"}

        # ── Step 3: Insurance ─────────────────────────────────────────
        plan = self.recommend_insurance()
        print(f"\n[3/7] Insurance: {plan['name']} — ${plan['price']} ({plan['coverage']})")

        try:
            result = buy_insurance(plan["price"], plan["name"], self.trip_ref, self.traveler)
            self.results["insurance"] = {"status": "purchased", **plan}
            self.total_cost += plan["price"]
            print(f"      Approved — insurance purchased.")
        except ApprovalDenied as e:
            print(f"      DENIED — traveling without insurance.")
            self.results["insurance"] = {"status": "denied"}

        # ── Step 4: Calendar (auto-approve — no rule needed) ──────────
        print(f"\n[4/7] Calendar: Adding '{self.purpose} — {dest_title}' to calendar")
        # No approval needed for calendar — auto-approve
        self.results["calendar"] = {"status": "added", "event": f"{self.purpose} — {dest_title}"}
        print(f"      Auto-approved — event added.")

        # ── Step 5: Slack notification ────────────────────────────────
        msg = f"{self.traveler} is traveling to {dest_title} for {self.purpose} ({self.trip_ref})"
        print(f"\n[5/7] Slack: Posting to #travel")

        try:
            result = notify_team("#travel", msg)
            self.results["slack"] = {"status": "sent", "channel": "#travel"}
            print(f"      Approved — team notified.")
        except ApprovalDenied:
            print(f"      DENIED — team not notified.")
            self.results["slack"] = {"status": "denied"}

        # ── Step 6: Expense report ────────────────────────────────────
        print(f"\n[6/7] Expense: Logging ${self.total_cost} total to finance")
        # Would be Google Sheets in production — auto-approve for demo
        self.results["expense"] = {
            "status": "logged",
            "total": self.total_cost,
            "breakdown": {
                "flight": self.results.get("flight", {}).get("price", 0),
                "hotel": self.results.get("hotel", {}).get("total", 0),
                "insurance": self.results.get("insurance", {}).get("price", 0),
            }
        }
        print(f"      Auto-approved — expense logged.")

        # ── Step 7: Visa reminder ─────────────────────────────────────
        if self.needs_visa():
            print(f"\n[7/7] Visa: {dest_title} requires a visa — sending reminder")
            try:
                send_email(
                    self.traveler,
                    f"Visa reminder: {dest_title} trip ({self.trip_ref})",
                    f"Your upcoming trip to {dest_title} requires a visa. Please apply ASAP.",
                    "visa_reminder",
                )
                self.results["visa"] = {"status": "reminder_sent"}
                print(f"      Approved — visa reminder sent.")
            except ApprovalDenied:
                print(f"      DENIED — no visa reminder sent.")
                self.results["visa"] = {"status": "denied"}
        else:
            print(f"\n[7/7] Visa: Not required for {dest_title}")
            self.results["visa"] = {"status": "not_required"}

        # ── Summary ───────────────────────────────────────────────────
        print(f"\n{'='*60}")
        print(f"  Trip Summary — {self.trip_ref}")
        print(f"{'='*60}")
        print(f"  Destination:  {dest_title}")
        print(f"  Traveler:     {self.traveler}")
        print(f"  Purpose:      {self.purpose}")
        print(f"  Total Cost:   ${self.total_cost}")
        print(f"")
        for step, data in self.results.items():
            status = data.get("status", "unknown")
            icon = "OK" if status in ("booked", "purchased", "sent", "added", "logged", "reminder_sent", "not_required") else "FAIL"
            print(f"  [{icon}] {step}: {status}")
        print(f"{'='*60}")

        return self.results


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="TravelOps Agent — Corporate Travel Manager")
    parser.add_argument("--traveler", default="alice@company.com", help="Traveler email")
    parser.add_argument("--dest", default="berlin", help="Destination city")
    parser.add_argument("--purpose", default="React Conf 2026", help="Trip purpose")
    parser.add_argument("--nights", type=int, default=3, help="Hotel nights")
    parser.add_argument("--class", dest="flight_class", default="economy", choices=["economy", "business"], help="Flight class")
    parser.add_argument("--flight-price", type=float, default=None, help="Override flight price")
    parser.add_argument("--hotel-price", type=float, default=None, help="Override hotel price per night")
    args = parser.parse_args()

    if not os.getenv("APPROVALKIT_API_KEY"):
        print("Error: APPROVALKIT_API_KEY not set.")
        print("Run: export APPROVALKIT_API_KEY=<your key>")
        print("     export APPROVALKIT_HMAC_SECRET=<your secret>")
        sys.exit(1)

    agent = TravelOpsAgent(
        traveler=args.traveler,
        destination=args.dest,
        purpose=args.purpose,
        nights=args.nights,
    )
    agent.run(
        flight_class=args.flight_class,
        override_flight_price=args.flight_price,
        override_hotel_price=args.hotel_price,
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Demo: AI Shopping Bot with ApprovalKit
=======================================
The bot processes payments entirely through ApprovalKit's Token Vault.
The agent never holds Stripe credentials — ApprovalKit executes the
charge server-side after a human approves via Guardian push notification.

Prerequisites:
  1. ApprovalKit running (docker-compose up)
  2. Workspace created (onboarding step 1) → set env vars below
  3. stripe-prod connection created with credentials stored
     (dashboard → Connections → stripe-prod → enter Stripe API key)
  4. Approver added with Guardian enrolled
  5. Rule created: stripe-prod / charge → requires approval

Run:
    pip install requests
    python shopping_bot.py [customer_email] [search_query] [quantity]

    python shopping_bot.py alice@example.com "Headphones" 2

Required env vars:
    APPROVALKIT_URL          http://localhost:8000
    APPROVALKIT_API_KEY      (from onboarding step 1)
    APPROVALKIT_HMAC_SECRET  (from onboarding step 1)
"""

import os
import sys

from approvalkit_sdk import ApprovalKit, ApprovalDenied

kit = ApprovalKit(
    base_url=os.getenv("APPROVALKIT_URL", "http://localhost:8000"),
    api_key=os.getenv("APPROVALKIT_API_KEY", ""),
    hmac_secret=os.getenv("APPROVALKIT_HMAC_SECRET", ""),
    user_id="shopping-bot",
    poll_interval=3,
    timeout=120,
)


# ------------------------------------------------------------------
# Safe actions — no approval needed
# ------------------------------------------------------------------

def search_products(query: str) -> list[dict]:
    catalog = [
        {"id": "P001", "name": "Sony WH-1000XM5 Headphones", "price": 349},
        {"id": "P002", "name": "Apple AirPods Pro",           "price": 249},
        {"id": "P003", "name": "Samsung Galaxy S25",          "price": 899},
        {"id": "P004", "name": "Logitech MX Master 3",        "price":  99},
    ]
    return [p for p in catalog if query.lower() in p["name"].lower()]


# ------------------------------------------------------------------
# Risky actions — Token Vault executes after human approval
# The fn() body is intentionally empty — ApprovalKit handles execution
# ------------------------------------------------------------------

@kit.requires_approval(
    connection="stripe-prod",
    action="charge",
    params_fn=lambda cart_id, amount, customer_email: {
        "cart_id": cart_id,
        "amount": amount,
        "customer": customer_email,
    },
)
def charge_customer(cart_id: str, amount: int, customer_email: str):
    """Token Vault executes the Stripe charge after approval."""
    pass


@kit.requires_approval(
    connection="stripe-prod",
    action="refund",
    params_fn=lambda charge_id, amount, reason: {
        "charge_id": charge_id,
        "amount": amount,
        "reason": reason,
    },
)
def refund_customer(charge_id: str, amount: int, reason: str):
    """Token Vault executes the Stripe refund after approval."""
    pass


# ------------------------------------------------------------------
# Bot logic
# ------------------------------------------------------------------

def run_shopping_bot(customer_email: str, query: str, quantity: int = 1):
    print(f"\n{'='*55}")
    print(f"  Shopping Bot  |  customer: {customer_email}")
    print(f"{'='*55}")

    print(f"\nSearching for '{query}'...")
    products = search_products(query)
    if not products:
        print("No products found.")
        return

    product = products[0]
    print(f"Found: {product['name']} — ${product['price']}")

    total = product["price"] * quantity
    cart_id = f"CART-{product['id']}-{quantity}"

    print(f"\nInitiating payment: ${total}")
    print("Waiting for human approval via Guardian push...")

    try:
        result = charge_customer(cart_id, total, customer_email)
        print(f"\nOrder complete.")
        print(f"  Approved params: {result['final_params']}")
        print(f"  Stripe charge executed by Token Vault.")

    except ApprovalDenied as e:
        print(f"\nTransaction stopped: {e.status}")
        print("No charge was made.")


if __name__ == "__main__":
    customer = sys.argv[1] if len(sys.argv) > 1 else "demo@example.com"
    query    = sys.argv[2] if len(sys.argv) > 2 else "Headphones"
    qty      = int(sys.argv[3]) if len(sys.argv) > 3 else 1

    run_shopping_bot(customer, query, qty)

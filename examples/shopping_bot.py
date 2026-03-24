"""
Demo: AI Shopping Bot with ApprovalKit
=======================================
Scenario: A shopping bot searches for products, adds them to a cart,
          and processes payments. High-risk actions (charge, refund)
          require human approval before executing.

Run:
    pip install requests
    python shopping_bot.py [customer_email] [search_query] [quantity]

    # example
    python shopping_bot.py alice@example.com "Headphones" 2

Required env vars (or edit the constants below):
    APPROVALKIT_URL          http://localhost:8000
    APPROVALKIT_API_KEY      (from scripts/setup.py output)
    APPROVALKIT_HMAC_SECRET  (from scripts/setup.py output)

Optional:
    DEMO_REFUND=1            also trigger a refund after the charge
"""

import os
import random
import sys
import time

from approvalkit_sdk import ApprovalKit, ApprovalDenied

# ------------------------------------------------------------------
# SDK setup — reads from env, falls back to empty strings
# ------------------------------------------------------------------

kit = ApprovalKit(
    base_url=os.getenv("APPROVALKIT_URL", "http://localhost:8000"),
    api_key=os.getenv("APPROVALKIT_API_KEY", ""),
    hmac_secret=os.getenv("APPROVALKIT_HMAC_SECRET", ""),
    user_id="auth0|shopping_bot_agent",
    poll_interval=3,
    timeout=120,
)

# ------------------------------------------------------------------
# Safe actions — no approval needed
# ------------------------------------------------------------------

def search_products(query: str) -> list[dict]:
    """Search the catalog. Read-only, no approval needed."""
    catalog = [
        {"id": "P001", "name": "Sony WH-1000XM5 Headphones", "price": 349, "stock": 5},
        {"id": "P002", "name": "Apple AirPods Pro",           "price": 249, "stock": 12},
        {"id": "P003", "name": "Samsung Galaxy S25",          "price": 899, "stock": 3},
        {"id": "P004", "name": "Logitech MX Master 3",        "price":  99, "stock": 8},
    ]
    return [p for p in catalog if query.lower() in p["name"].lower()]


def add_to_cart(product_id: str, quantity: int, customer_email: str) -> dict:
    """Add item to cart. No approval needed."""
    cart_id = f"CART_{random.randint(1000, 9999)}"
    print(f"   Cart created: {cart_id}")
    return {"cart_id": cart_id, "product_id": product_id, "qty": quantity}


# ------------------------------------------------------------------
# Risky actions — wrapped with @requires_approval
# Adding the decorator is the ONLY change from the original bot.
# ------------------------------------------------------------------

@kit.requires_approval(
    connection="stripe-prod",
    action="charge",
    params_fn=lambda cart_id, amount, customer_email: {
        "cart_id": cart_id,
        "amount_usd": amount,
        "customer": customer_email,
    },
)
def charge_customer(cart_id: str, amount: int, customer_email: str) -> dict:
    """Charge the customer via Stripe. Runs only after human approval."""
    # In production: result = stripe.PaymentIntent.create(amount=amount*100, ...)
    charge_id = f"ch_{random.randint(10000, 99999)}"
    print(f"   Stripe charged: ${amount} → {customer_email}  (id={charge_id})")
    return {"charge_id": charge_id, "status": "succeeded"}


@kit.requires_approval(
    connection="stripe-prod",
    action="refund",
    params_fn=lambda charge_id, amount, reason: {
        "charge_id": charge_id,
        "amount_usd": amount,
        "reason": reason,
    },
)
def refund_customer(charge_id: str, amount: int, reason: str) -> dict:
    """Issue a refund via Stripe. Runs only after human approval."""
    # In production: result = stripe.Refund.create(payment_intent=charge_id)
    refund_id = f"re_{random.randint(10000, 99999)}"
    print(f"   Stripe refunded: ${amount}  (id={refund_id})")
    return {"refund_id": refund_id, "status": "succeeded"}


# ------------------------------------------------------------------
# Bot logic — unchanged from a bot without any approval gates
# ------------------------------------------------------------------

def run_shopping_bot(customer_email: str, query: str, quantity: int = 1):
    print(f"\n{'='*60}")
    print(f"  Shopping Bot  |  customer: {customer_email}")
    print(f"{'='*60}")

    # 1. Search
    print(f"\nSearching for '{query}'...")
    products = search_products(query)
    if not products:
        print("No products found.")
        return
    product = products[0]
    print(f"Found: {product['name']} — ${product['price']}")

    # 2. Add to cart
    print(f"\nAdding {quantity}x to cart...")
    cart = add_to_cart(product["id"], quantity, customer_email)

    total = product["price"] * quantity

    # 3. Charge — approval gate fires here
    print(f"\nInitiating payment: ${total}")
    try:
        result = charge_customer(cart["cart_id"], total, customer_email)
        print(f"\nOrder complete. Charge ID: {result['charge_id']}")

        # 4. Optional refund demo
        if os.getenv("DEMO_REFUND"):
            print(f"\nSimulating a refund request...")
            time.sleep(1)
            refund_customer(result["charge_id"], total, "customer request")
            print("Refund complete.")

    except ApprovalDenied as e:
        print(f"\nTransaction stopped: approval {e.status}")
        print("The bot did not charge the customer.")


# ------------------------------------------------------------------
# Alternative: inline kit.gate() without a decorator
# ------------------------------------------------------------------

def run_with_inline_gate(customer_email: str, product_id: str, amount: int):
    """
    Use kit.gate() when you need approval inside a conditional branch
    rather than at the function entry point.
    """
    print("\n--- inline gate() example ---")
    try:
        kit.gate("stripe-prod", "charge", {
            "product_id": product_id,
            "amount_usd": amount,
            "customer": customer_email,
        })
        # Reaching this line means approved
        print(f"Approved — charging ${amount} to {customer_email}")
        # stripe.charge(...)
    except ApprovalDenied as e:
        print(f"Denied: {e}")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    customer = sys.argv[1] if len(sys.argv) > 1 else "demo@example.com"
    query    = sys.argv[2] if len(sys.argv) > 2 else "Headphones"
    qty      = int(sys.argv[3]) if len(sys.argv) > 3 else 1

    run_shopping_bot(customer, query, qty)

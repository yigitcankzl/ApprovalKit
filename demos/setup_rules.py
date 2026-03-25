"""
Demo Rule Setup
===============
Creates all connections, approvers, and rules needed for the
ecommerce_agent.py and hr_agent.py demos.

Run once before running the demo agents:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    python demos/setup_rules.py
"""

import json
import os
import sys
import uuid

import requests

BASE_URL = os.environ.get("APPROVALKIT_URL", "http://localhost:8000")
API_KEY  = os.environ.get("APPROVALKIT_API_KEY", "")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


def post(path: str, body: dict) -> dict:
    r = requests.post(f"{BASE_URL}{path}", json=body, headers=HEADERS)
    if r.status_code not in (200, 201):
        print(f"  [WARN] {path} → {r.status_code}: {r.text[:200]}")
        return {}
    return r.json()


def get(path: str) -> list:
    r = requests.get(f"{BASE_URL}{path}", headers=HEADERS)
    return r.json() if r.ok else []


def section(title: str):
    print(f"\n{'─'*55}")
    print(f"  {title}")
    print(f"{'─'*55}")


# ── Step 1: Connections ───────────────────────────────────────────────────────

CONNECTIONS = [
    {"name": "Stripe Production", "service": "stripe", "slug": "stripe-prod",
     "actions": ["charge", "refund"]},
    {"name": "Slack Production",  "service": "slack",  "slug": "slack-prod",
     "actions": ["send_message"]},
    {"name": "Gmail Production",  "service": "gmail",  "slug": "gmail-prod",
     "actions": ["send_email"]},
    {"name": "GitHub Production", "service": "github", "slug": "github-prod",
     "actions": ["add_member", "remove_member", "deploy"]},
]

def create_connections():
    section("Creating connections")
    ids = {}
    existing = {c["slug"]: c["id"] for c in get("/api/v1/connections")}
    for c in CONNECTIONS:
        if c["slug"] in existing:
            print(f"  [skip] {c['slug']} already exists")
            ids[c["slug"]] = existing[c["slug"]]
            continue
        result = post("/api/v1/connections", c)
        if result.get("id"):
            ids[c["slug"]] = result["id"]
            print(f"  [ok]   {c['slug']}")
    return ids


# ── Step 2: Approvers ─────────────────────────────────────────────────────────

APPROVERS = [
    # E-commerce
    {"name": "Sales Manager",   "email": "sales_manager@example.com",
     "auth0_user_id": "auth0|sales_manager",  "role": "sales_manager"},
    {"name": "CFO",             "email": "cfo@example.com",
     "auth0_user_id": "auth0|cfo",            "role": "cfo"},
    {"name": "CS Agent",        "email": "cs_agent@example.com",
     "auth0_user_id": "auth0|cs_agent",       "role": "cs_agent"},
    {"name": "CS Manager",      "email": "cs_manager@example.com",
     "auth0_user_id": "auth0|cs_manager",     "role": "cs_manager"},
    {"name": "Team Lead",       "email": "team_lead@example.com",
     "auth0_user_id": "auth0|team_lead",      "role": "team_lead"},
    # HR
    {"name": "HR Manager",      "email": "hr_manager@example.com",
     "auth0_user_id": "auth0|hr_manager",     "role": "hr_manager"},
    {"name": "CEO",             "email": "ceo@example.com",
     "auth0_user_id": "auth0|ceo",            "role": "ceo"},
    {"name": "IT Manager",      "email": "it_manager@example.com",
     "auth0_user_id": "auth0|it_manager",     "role": "it_manager"},
    {"name": "CTO",             "email": "cto@example.com",
     "auth0_user_id": "auth0|cto",            "role": "cto"},
]

def create_approvers():
    section("Creating approvers")
    by_role = {}
    existing = {a["auth0_user_id"]: a["id"] for a in get("/api/v1/approvers")}
    for a in APPROVERS:
        if a["auth0_user_id"] in existing:
            print(f"  [skip] {a['name']} already exists")
            by_role[a["role"]] = existing[a["auth0_user_id"]]
            continue
        result = post("/api/v1/approvers", {
            "name": a["name"],
            "email": a["email"],
            "auth0_user_id": a["auth0_user_id"],
            "notify_channel": ["guardian_push"],
            "urgent_channel": ["guardian_push"],
        })
        if result.get("id"):
            by_role[a["role"]] = result["id"]
            print(f"  [ok]   {a['name']}")
    return by_role


# ── Step 3: Rules ─────────────────────────────────────────────────────────────

def build_rules(approvers: dict) -> list:
    sm  = approvers.get("sales_manager", "")
    cfo = approvers.get("cfo", "")
    csa = approvers.get("cs_agent", "")
    csm = approvers.get("cs_manager", "")
    tl  = approvers.get("team_lead", "")
    hr  = approvers.get("hr_manager", "")
    ceo = approvers.get("ceo", "")
    itm = approvers.get("it_manager", "")
    cto = approvers.get("cto", "")

    return [
        # ── E-Commerce ────────────────────────────────────────────────

        {
            "name": "[Ecom] Stripe charge — medium ($100-$999)",
            "connection": "stripe-prod",
            "action": "charge",
            "model": "any_one",
            "timeout_seconds": 300,
            "context_template": "Charge ${amount_usd} for {customer} — {description}",
            "condition": "params.get('amount_usd', 0) >= 100 and params.get('amount_usd', 0) < 1000",
            "approver_ids": [sm],
        },
        {
            "name": "[Ecom] Stripe charge — large ($1000+) STEP-UP",
            "connection": "stripe-prod",
            "action": "charge",
            "model": "all_of_n",
            "timeout_seconds": 600,
            "context_template": "LARGE charge ${amount_usd} for {customer} — {description}",
            "condition": "params.get('amount_usd', 0) >= 1000",
            "approver_ids": [sm, cfo],
        },
        {
            "name": "[Ecom] Stripe refund — small (<$50)",
            "connection": "stripe-prod",
            "action": "refund",
            "model": "any_one",
            "timeout_seconds": 300,
            "context_template": "Refund ${amount_usd} for {customer} — {reason}",
            "condition": "params.get('amount_usd', 0) < 50",
            "approver_ids": [csa],
        },
        {
            "name": "[Ecom] Stripe refund — large ($50+) with partial approval",
            "connection": "stripe-prod",
            "action": "refund",
            "model": "specific",
            "timeout_seconds": 300,
            "context_template": "Refund ${amount_usd} for {customer} — {reason}",
            "condition": "params.get('amount_usd', 0) >= 50",
            "approver_ids": [csm],
        },
        {
            "name": "[Ecom] Slack #general",
            "connection": "slack-prod",
            "action": "send_message",
            "model": "any_one",
            "timeout_seconds": 300,
            "context_template": "Post to {channel}: {message}",
            "condition": "params.get('channel') == '#general'",
            "approver_ids": [tl],
        },
        {
            "name": "[Ecom] Slack #finance",
            "connection": "slack-prod",
            "action": "send_message",
            "model": "specific",
            "timeout_seconds": 300,
            "context_template": "Post to {channel}: {message}",
            "condition": "params.get('channel') == '#finance'",
            "approver_ids": [cfo],
        },

        # ── HR ────────────────────────────────────────────────────────

        {
            "name": "[HR] Gmail offer letter",
            "connection": "gmail-prod",
            "action": "send_email",
            "model": "specific",
            "timeout_seconds": 600,
            "context_template": "Send {type} to {recipient}: {subject}",
            "condition": "params.get('type') == 'offer_letter'",
            "approver_ids": [hr],
        },
        {
            "name": "[HR] Gmail termination letter",
            "connection": "gmail-prod",
            "action": "send_email",
            "model": "all_of_n",
            "timeout_seconds": 900,
            "context_template": "TERMINATION email to {recipient}: {subject}",
            "condition": "params.get('type') == 'termination'",
            "approver_ids": [hr, ceo],
        },
        {
            "name": "[HR] Slack #general",
            "connection": "slack-prod",
            "action": "send_message",
            "model": "any_one",
            "timeout_seconds": 300,
            "context_template": "HR post to {channel}: {message}",
            "condition": "params.get('channel') == '#general'",
            "approver_ids": [hr],
        },
        {
            "name": "[HR] Slack #hr channel",
            "connection": "slack-prod",
            "action": "send_message",
            "model": "specific",
            "timeout_seconds": 300,
            "context_template": "HR post to {channel}: {message}",
            "condition": "params.get('channel') == '#hr'",
            "approver_ids": [hr],
        },
        {
            "name": "[HR] GitHub add member (role=member)",
            "connection": "github-prod",
            "action": "add_member",
            "model": "specific",
            "timeout_seconds": 300,
            "context_template": "Add {username} to {org} as {role}",
            "condition": "params.get('role', 'member') == 'member'",
            "approver_ids": [itm],
        },
        {
            "name": "[HR] GitHub add member (role=admin) — IT + CTO",
            "connection": "github-prod",
            "action": "add_member",
            "model": "all_of_n",
            "timeout_seconds": 600,
            "context_template": "Add {username} to {org} as ADMIN",
            "condition": "params.get('role') == 'admin'",
            "approver_ids": [itm, cto],
        },
        {
            "name": "[HR] GitHub remove member — IT + HR",
            "connection": "github-prod",
            "action": "remove_member",
            "model": "all_of_n",
            "timeout_seconds": 600,
            "context_template": "Remove {username} from {org} — {reason}",
            "approver_ids": [itm, hr],
        },
    ]


def create_rules(approvers: dict):
    section("Creating rules")
    rules = build_rules(approvers)
    for rule in rules:
        approver_ids = [aid for aid in rule.pop("approver_ids", []) if aid]
        condition    = rule.pop("condition", None)
        body = {**rule, "is_active": True}
        result = post("/api/v1/rules", body)
        rule_id = result.get("id")
        if not rule_id:
            print(f"  [fail] {rule['name']}")
            continue
        print(f"  [ok]   {rule['name']}")

        # Assign approvers
        for approver_id in approver_ids:
            requests.post(
                f"{BASE_URL}/api/v1/rules/{rule_id}/approvers",
                json={"approver_id": approver_id},
                headers=HEADERS,
            )


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*55)
    print("  ApprovalKit Demo Rule Setup")
    print("  Target:", BASE_URL)
    print("="*55)

    if not API_KEY:
        print("\n[ERROR] APPROVALKIT_API_KEY is not set.")
        sys.exit(1)

    create_connections()
    approvers = create_approvers()
    create_rules(approvers)

    print("\n" + "="*55)
    print("  Setup complete!")
    print("  Dashboard: http://localhost:3000/rules")
    print("="*55 + "\n")

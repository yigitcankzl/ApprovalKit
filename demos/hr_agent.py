"""
Demo Agent 2 — HR
=================
Simulates an AI HR assistant that sends offer letters, manages
team communications, and handles GitHub org membership.
Every sensitive action requires human approval.

Rule configuration (set up via dashboard or setup_rules.py):

  gmail-prod : send_email
    type=invite       → no rule  (auto-approved)
    type=offer_letter → specific [hr_manager]
    type=termination  → all_of_n [hr_manager, ceo]

  slack-prod : send_message
    channel=#general  → any_one  [hr_manager]
    channel=#hr       → specific [hr_manager]

  github-prod : add_member
    role=member       → specific [it_manager]
    role=admin        → all_of_n [it_manager, cto]

  github-prod : remove_member
    (any)             → all_of_n [it_manager, hr_manager]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/hr_agent.py
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
    user_id="auth0|hr_agent",
    poll_interval=3,
    timeout=180,
)

# ── Action definitions ────────────────────────────────────────────────────────

@kit.requires_approval(
    connection="gmail-prod",
    action="send_email",
    params_fn=lambda recipient, subject, email_type, body="": {
        "recipient": recipient,
        "subject": subject,
        "type": email_type,
        "body_preview": body[:120] + ("..." if len(body) > 120 else ""),
    },
)
def send_email(recipient: str, subject: str, email_type: str, body: str = "") -> dict:
    """
    Send an email via Gmail.
    - invite       → auto-approved
    - offer_letter → HR Manager must approve
    - termination  → HR Manager + CEO must both approve
    """
    return {"sent_to": recipient, "subject": subject, "type": email_type}


@kit.requires_approval(
    connection="slack-prod",
    action="send_message",
    params_fn=lambda channel, message: {
        "channel": channel,
        "message": message,
    },
)
def post_slack(channel: str, message: str) -> dict:
    """Post to Slack. #hr channel requires HR Manager approval."""
    return {"channel": channel, "posted": True}


@kit.requires_approval(
    connection="github-prod",
    action="add_member",
    params_fn=lambda username, org, role: {
        "username": username,
        "org": org,
        "role": role,
    },
)
def add_github_member(username: str, org: str, role: str = "member") -> dict:
    """
    Add a user to the GitHub org.
    - member → IT Manager approves
    - admin  → IT Manager + CTO must both approve
    """
    return {"added": username, "org": org, "role": role}


@kit.requires_approval(
    connection="github-prod",
    action="remove_member",
    params_fn=lambda username, org, reason: {
        "username": username,
        "org": org,
        "reason": reason,
    },
)
def remove_github_member(username: str, org: str, reason: str) -> dict:
    """
    Remove a user from the GitHub org.
    Always requires IT Manager + HR Manager (all_of_n).
    """
    return {"removed": username, "org": org}


# ── Scenarios ─────────────────────────────────────────────────────────────────

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  HR Agent Demo")
    print("="*60)

    # ── Scenario 1: Calendar invite — no rule, auto-approved ──────────
    scenario("Scenario 1: Interview invite — no rule, auto-approved")
    try:
        result = send_email(
            recipient="candidate@example.com",
            subject="Interview Invitation — Software Engineer",
            email_type="invite",
            body="We'd like to invite you for an interview on Friday at 2pm.",
        )
        print(f"  Sent '{result['subject']}' to {result['sent_to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 2: Offer letter — HR Manager must approve ────────────
    scenario("Scenario 2: Offer letter — HR Manager approval required")
    try:
        result = send_email(
            recipient="newjoin@example.com",
            subject="Offer Letter — Senior Engineer, $180,000",
            email_type="offer_letter",
            body="We are pleased to offer you the position of Senior Engineer with a base salary of $180,000.",
        )
        print(f"  Sent '{result['subject']}' to {result['sent_to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 3: Termination letter — HR Manager + CEO ─────────────
    scenario("Scenario 3: Termination letter — HR Manager + CEO (all_of_n)")
    print("  Both HR Manager and CEO must approve.")
    try:
        result = send_email(
            recipient="employee@example.com",
            subject="Employment Termination Notice",
            email_type="termination",
            body="We regret to inform you that your employment is terminated effective immediately.",
        )
        print(f"  Sent '{result['subject']}' to {result['sent_to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 4: Post to #hr channel — HR Manager only ─────────────
    scenario("Scenario 4: Slack post to #hr — HR Manager approval")
    try:
        result = post_slack(
            channel="#hr",
            message="Reminder: Q2 performance reviews due by Friday.",
        )
        print(f"  Posted to {result['channel']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 5: GitHub — add new employee as member ───────────────
    scenario("Scenario 5: GitHub add_member (role=member) — IT Manager")
    try:
        result = add_github_member("newdev", "acme-corp", role="member")
        print(f"  Added {result['added']} to {result['org']} as {result['role']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 6: GitHub — promote to admin — IT Manager + CTO ──────
    scenario("Scenario 6: GitHub add_member (role=admin) — IT Manager + CTO")
    print("  Both IT Manager and CTO must approve.")
    try:
        result = add_github_member("seniordev", "acme-corp", role="admin")
        print(f"  Added {result['added']} to {result['org']} as {result['role']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 7: GitHub — remove terminated employee ───────────────
    scenario("Scenario 7: GitHub remove_member — IT Manager + HR Manager")
    print("  Off-boarding: IT Manager and HR Manager must both confirm.")
    try:
        result = remove_github_member("employee", "acme-corp", reason="Employment terminated")
        print(f"  Removed {result['removed']} from {result['org']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

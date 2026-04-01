"""
Demo Agent — API Key Rotation
==============================
Simulates an AI agent that rotates API keys for services. Scheduled
rotations are auto-approved. Emergency rotations require the security
lead. Third-party key rotations (which affect external partners)
require CTO approval.

Rule configuration:

  github-prod : deploy
    rotation_type=scheduled     -> no rule (auto-approved)
    rotation_type=emergency     -> specific [security_lead]
    rotation_type=third_party   -> specific [cto]

  slack-prod : send_message
    channel=#security           -> any_one [security_engineer]
    channel=#engineering        -> specific [engineering_manager]

  gmail-prod : send_email
    recipient=partner           -> specific [cto]
    recipient=internal          -> any_one [security_lead]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/api-key-rotation-agent/agent.py
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
    user_id="auth0|api_key_rotation_agent",
    poll_interval=3,
    timeout=180,
)

# ── Simulated data ────────────────────────────────────────────────────────────

KEYS = {
    "stripe-api-key": {
        "service": "payments",
        "provider": "Stripe",
        "last_rotated": "2025-12-01",
        "rotation_policy_days": 90,
    },
    "sendgrid-api-key": {
        "service": "email-service",
        "provider": "SendGrid",
        "last_rotated": "2025-11-15",
        "rotation_policy_days": 90,
    },
    "twilio-api-key": {
        "service": "sms-gateway",
        "provider": "Twilio",
        "last_rotated": "2025-10-01",
        "rotation_policy_days": 60,
    },
    "aws-iam-key": {
        "service": "infrastructure",
        "provider": "AWS",
        "last_rotated": "2026-03-01",
        "rotation_policy_days": 30,
    },
}

# ── Action definitions ────────────────────────────────────────────────────────

@kit.requires_approval(
    connection="github-prod",
    action="deploy",
    params_fn=lambda key_name, service, rotation_type, provider: {
        "key_name": key_name,
        "service": service,
        "rotation_type": rotation_type,
        "provider": provider,
    },
)
def rotate_key(key_name: str, service: str, rotation_type: str, provider: str) -> dict:
    """Rotate an API key via Token Vault. Approval level depends on rotation type."""
    return {
        "key_name": key_name,
        "service": service,
        "rotation_type": rotation_type,
        "rotated": True,
    }


@kit.requires_approval(
    connection="slack-prod",
    action="send_message",
    params_fn=lambda channel, message: {
        "channel": channel,
        "message": message,
    },
)
def notify_slack(channel: str, message: str) -> dict:
    """Post a key rotation notification to Slack."""
    return {"channel": channel, "posted": True}


@kit.requires_approval(
    connection="gmail-prod",
    action="send_email",
    params_fn=lambda to_email, subject, body: {
        "to": to_email,
        "subject": subject,
        "body": body,
    },
)
def send_email(to_email: str, subject: str, body: str) -> dict:
    """Send an email notification about key rotation to a partner or team."""
    return {"to": to_email, "sent": True}


# ── Scenarios ─────────────────────────────────────────────────────────────────

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  API Key Rotation Agent Demo")
    print("="*60)

    # ── Scenario 1: Scheduled rotation — auto-approved ────────────────
    key = KEYS["aws-iam-key"]
    scenario("Scenario 1: Scheduled AWS IAM rotation — auto-approved")
    try:
        result = rotate_key(
            "aws-iam-key",
            key["service"],
            "scheduled",
            key["provider"],
        )
        print(f"  Rotated: {result['key_name']} ({result['rotation_type']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 2: Emergency rotation — security_lead approval ───────
    key = KEYS["stripe-api-key"]
    scenario("Scenario 2: Emergency Stripe key rotation — security_lead required")
    print("  Suspicious activity detected on payment processing endpoint.")
    try:
        result = rotate_key(
            "stripe-api-key",
            key["service"],
            "emergency",
            key["provider"],
        )
        print(f"  Rotated: {result['key_name']} ({result['rotation_type']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 3: Third-party rotation — CTO approval ──────────────
    key = KEYS["twilio-api-key"]
    scenario("Scenario 3: Twilio key rotation (third-party) — CTO required")
    print("  This rotation affects external partner integrations.")
    try:
        result = rotate_key(
            "twilio-api-key",
            key["service"],
            "third_party",
            key["provider"],
        )
        print(f"  Rotated: {result['key_name']} ({result['rotation_type']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 4: Email partner about rotation ─────────────────────
    scenario("Scenario 4: Email Twilio partner — CTO approval for external comms")
    try:
        result = send_email(
            "integrations@twilio.com",
            "API Key Rotation Notice - SMS Gateway",
            "Your API key for our SMS gateway integration has been rotated. "
            "Please update your webhook configuration with the new credentials "
            "provided via your secure dashboard.",
        )
        print(f"  Email sent to {result['to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 5: Notify #security about rotation batch ────────────
    scenario("Scenario 5: Notify #security — rotation summary")
    try:
        result = notify_slack(
            "#security",
            "Key rotation batch: aws-iam-key (auto), stripe-api-key (emergency, approved), "
            "twilio-api-key (third-party, pending CTO).",
        )
        print(f"  Posted to {result['channel']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 6: Scheduled SendGrid rotation — auto-approved ──────
    key = KEYS["sendgrid-api-key"]
    scenario("Scenario 6: Scheduled SendGrid rotation — auto-approved")
    try:
        result = rotate_key(
            "sendgrid-api-key",
            key["service"],
            "scheduled",
            key["provider"],
        )
        print(f"  Rotated: {result['key_name']} ({result['rotation_type']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

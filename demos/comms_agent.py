"""
Demo Agent — Communications
============================
Simulates a marketing/PR agent that sends emails, posts to Slack,
and issues press releases. Audience size and content type determine
the approval chain.

Rules:
  gmail-prod : send_email
    recipient_count <= 10   → no rule (auto)
    recipient_count > 10    → any_one [manager]
    recipient_count > 100   → sequential [marketing_lead → legal]

  slack-prod : send_message
    channel=#general        → any_one [manager]
    channel=#announcements  → specific [ceo]

  gmail-prod : press_release
    (any)                   → sequential [pr_manager → legal → ceo]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/comms_agent.py
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
    user_id="auth0|comms_agent",
    poll_interval=3,
    timeout=180,
)

# ── Actions ───────────────────────────────────────────────────────────────────

@kit.requires_approval(
    connection="gmail-prod",
    action="send_email",
    params_fn=lambda subject, recipient_count, audience_type, preview: {
        "subject": subject,
        "recipient_count": recipient_count,
        "audience_type": audience_type,
        "body_preview": preview[:120] + ("..." if len(preview) > 120 else ""),
    },
)
def send_email_campaign(
    subject: str, recipient_count: int, audience_type: str, preview: str
) -> dict:
    """Send a bulk email. Large audience requires sequential approval."""
    return {"sent": recipient_count, "subject": subject}


@kit.requires_approval(
    connection="slack-prod",
    action="send_message",
    params_fn=lambda channel, message: {
        "channel": channel,
        "message": message,
    },
)
def post_slack(channel: str, message: str) -> dict:
    """Post to Slack. #announcements requires CEO approval."""
    return {"channel": channel, "posted": True}


@kit.requires_approval(
    connection="gmail-prod",
    action="press_release",
    params_fn=lambda headline, embargo_until, distribution: {
        "headline": headline,
        "embargo_until": embargo_until,
        "distribution": distribution,
    },
)
def issue_press_release(headline: str, embargo_until: str, distribution: str) -> dict:
    """Issue a press release. Always goes PR Manager → Legal → CEO."""
    return {"issued": headline, "distribution": distribution}


# ── Scenarios ─────────────────────────────────────────────────────────────────

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Communications Agent Demo")
    print("="*60)

    scenario("Scenario 1: Internal email (8 recipients) — auto-approved")
    try:
        result = send_email_campaign(
            subject="Team lunch this Friday at noon",
            recipient_count=8,
            audience_type="internal",
            preview="Hi everyone, we're having a team lunch this Friday at noon in the main office.",
        )
        print(f"  Sent '{result['subject']}' to {result['sent']} recipients")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    scenario("Scenario 2: Client newsletter (45 recipients) — manager approval")
    try:
        result = send_email_campaign(
            subject="Product Update — March 2026",
            recipient_count=45,
            audience_type="clients",
            preview="We're excited to share our latest product updates, including new approval models and SDK improvements.",
        )
        print(f"  Sent '{result['subject']}' to {result['sent']} recipients")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    scenario("Scenario 3: Mass email (12,500 recipients) — marketing_lead → legal (sequential)")
    print("  Large audience: full compliance review required.")
    try:
        result = send_email_campaign(
            subject="Introducing ApprovalKit 2.0 — Now Generally Available",
            recipient_count=12500,
            audience_type="subscribers",
            preview="ApprovalKit 2.0 is live. New features include k-of-n quorum, Auth0 Token Vault, and a pip-installable SDK.",
        )
        print(f"  Sent '{result['subject']}' to {result['sent']} recipients")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    scenario("Scenario 4: Slack #announcements — CEO approval required")
    try:
        result = post_slack(
            channel="#announcements",
            message="ApprovalKit 2.0 is now generally available. Read the blog post for details.",
        )
        print(f"  Posted to {result['channel']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    scenario("Scenario 5: Press release — PR Manager → Legal → CEO (sequential)")
    print("  Three-step chain before going public.")
    try:
        result = issue_press_release(
            headline="ApprovalKit Raises $8M Seed to Build Human Oversight Infrastructure for AI Agents",
            embargo_until="2026-04-01T09:00:00Z",
            distribution="Business Wire, TechCrunch, Reuters",
        )
        print(f"  Issued: '{result['issued']}'")
        print(f"  Distribution: {result['distribution']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

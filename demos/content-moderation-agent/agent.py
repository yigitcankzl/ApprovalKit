"""
Demo Agent — Content Moderation (Media)
========================================
Simulates an AI agent that moderates user-generated content
with escalating enforcement actions.

Rule configuration:

  moderation-svc : moderation
    type=spam            -> no rule  (auto-approved)
    type=suspicious      -> any_one  [moderator]
    type=account_ban     -> all_of_n [senior_moderator, legal]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/content-moderation-agent/agent.py
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
    user_id="auth0|content_moderation_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

REPORTS = {
    "RPT-9001": {
        "user": "spambot_42",
        "content_type": "comment",
        "content_preview": "Buy cheap watches at scam-link.com!!!",
        "confidence": 0.99,
        "prior_violations": 12,
    },
    "RPT-9002": {
        "user": "user_8837",
        "content_type": "post",
        "content_preview": "Content flagged by automated hate-speech detector",
        "confidence": 0.72,
        "prior_violations": 1,
    },
    "RPT-9003": {
        "user": "influencer_mega",
        "content_type": "account",
        "content_preview": "Repeated policy violations; 3 strikes exceeded",
        "confidence": 0.95,
        "prior_violations": 8,
        "followers": 250000,
    },
}

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="moderation-svc",
    action="moderation",
    params_fn=lambda report_id: {
        "report_id": report_id,
        "user": REPORTS[report_id]["user"],
        "content_type": REPORTS[report_id]["content_type"],
        "content_preview": REPORTS[report_id]["content_preview"],
        "confidence": REPORTS[report_id]["confidence"],
        "type": "spam",
    },
)
def remove_spam(report_id: str) -> dict:
    """
    Remove obvious spam content.
    Auto-approved -- high-confidence automated detection.
    """
    report = REPORTS[report_id]
    return {
        "report_id": report_id,
        "user": report["user"],
        "action": "content_removed",
        "confidence": report["confidence"],
    }


@kit.requires_approval(
    connection="moderation-svc",
    action="moderation",
    params_fn=lambda report_id: {
        "report_id": report_id,
        "user": REPORTS[report_id]["user"],
        "content_type": REPORTS[report_id]["content_type"],
        "content_preview": REPORTS[report_id]["content_preview"],
        "confidence": REPORTS[report_id]["confidence"],
        "prior_violations": REPORTS[report_id]["prior_violations"],
        "type": "suspicious",
    },
)
def review_suspicious(report_id: str) -> dict:
    """
    Flag suspicious content for human review.
    Requires moderator approval before action is taken.
    """
    report = REPORTS[report_id]
    return {
        "report_id": report_id,
        "user": report["user"],
        "action": "reviewed_and_actioned",
    }


@kit.requires_approval(
    connection="moderation-svc",
    action="moderation",
    params_fn=lambda report_id, justification: {
        "report_id": report_id,
        "user": REPORTS[report_id]["user"],
        "content_preview": REPORTS[report_id]["content_preview"],
        "prior_violations": REPORTS[report_id]["prior_violations"],
        "followers": REPORTS[report_id].get("followers", 0),
        "type": "account_ban",
        "justification": justification,
    },
)
def ban_account(report_id: str, justification: str) -> dict:
    """
    Permanently ban a user account.
    Requires both senior_moderator AND legal approval (all_of_n).
    """
    report = REPORTS[report_id]
    return {
        "report_id": report_id,
        "user": report["user"],
        "action": "account_banned",
        "followers_affected": report.get("followers", 0),
    }


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Content Moderation Agent Demo")
    print("="*60)

    # -- Scenario 1: Spam removal -- auto-approved ---
    scenario("Scenario 1: Spam removal -- auto-approved (99% confidence)")
    try:
        result = remove_spam("RPT-9001")
        print(f"  Removed: content by {result['user']}")
        print(f"  Confidence: {result['confidence']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 2: Suspicious content -- moderator ---
    scenario("Scenario 2: Suspicious content (72% confidence) -- moderator review")
    try:
        result = review_suspicious("RPT-9002")
        print(f"  Reviewed: {result['user']}")
        print(f"  Action: {result['action']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # -- Scenario 3: Account ban -- senior_moderator + legal ---
    scenario("Scenario 3: Account ban (250k followers) -- senior_mod + legal")
    print("  Both senior_moderator and legal must approve.")
    try:
        result = ban_account(
            "RPT-9003",
            "3-strike policy exceeded; 8 violations documented"
        )
        print(f"  Banned: {result['user']}")
        print(f"  Followers affected: {result['followers_affected']:,}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

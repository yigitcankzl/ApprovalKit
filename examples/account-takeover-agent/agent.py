"""
Demo Agent -- Account Takeover Response
=========================================
Simulates an AI security agent that responds to suspected account
takeover events: alerting the user, freezing compromised accounts,
and issuing permanent bans. Each action is gated via ApprovalKit.

Rule configuration (set up via dashboard or setup_rules.py):

  gmail-prod : alert
    any account            -> no rule  (auto-approved)

  salesforce-prod : freeze_account
    any account            -> specific [security_lead]

  salesforce-prod : permanent_ban
    any account            -> all_of_n [security_lead, legal_counsel]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python examples/account-takeover-agent/agent.py
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
    user_id="auth0|account_takeover_agent",
    poll_interval=3,
    timeout=180,
)

# -- Simulated data -----------------------------------------------------------

ACCOUNTS = [
    {"user": "alice.chen@gmail.com", "account_id": "ACC-10421", "tier": "standard", "risk_score": 85},
    {"user": "business@bigretail.com", "account_id": "ACC-00312", "tier": "enterprise", "risk_score": 95},
    {"user": "spammer@disposable.net", "account_id": "ACC-99871", "tier": "free", "risk_score": 99},
]

THREAT_INDICATORS = [
    {"account_id": "ACC-10421", "signals": ["login_from_new_country", "password_change", "email_change_attempt"], "severity": "medium"},
    {"account_id": "ACC-00312", "signals": ["impossible_travel", "bulk_data_export", "api_key_rotation"], "severity": "high"},
    {"account_id": "ACC-99871", "signals": ["bot_pattern", "spam_reported_50x", "fake_payment_methods", "ToS_violation"], "severity": "critical"},
]

# -- Action definitions --------------------------------------------------------

@kit.requires_approval(
    connection="gmail-prod",
    action="alert",
    params_fn=lambda user_email, account_id, signals, severity: {
        "user_email": user_email,
        "account_id": account_id,
        "threat_signals": signals,
        "severity": severity,
    },
)
def send_takeover_alert(user_email: str, account_id: str,
                        signals: list, severity: str) -> dict:
    """
    Send account takeover alert email to user.
    Auto-approved -- time-critical notification.
    """
    return {"alerted": True, "user": user_email, "severity": severity}


@kit.requires_approval(
    connection="salesforce-prod",
    action="freeze_account",
    params_fn=lambda user_email, account_id, signals, severity, reason: {
        "user_email": user_email,
        "account_id": account_id,
        "threat_signals": signals,
        "severity": severity,
        "freeze_reason": reason,
    },
)
def freeze_account(user_email: str, account_id: str, signals: list,
                   severity: str, reason: str) -> dict:
    """
    Freeze a compromised account pending investigation.
    Requires Security Lead approval.
    """
    return {"frozen": True, "account_id": account_id, "user": user_email}


@kit.requires_approval(
    connection="salesforce-prod",
    action="permanent_ban",
    params_fn=lambda user_email, account_id, signals, violations, ban_reason: {
        "user_email": user_email,
        "account_id": account_id,
        "threat_signals": signals,
        "violations": violations,
        "ban_reason": ban_reason,
    },
)
def permanent_ban(user_email: str, account_id: str, signals: list,
                  violations: list, ban_reason: str) -> dict:
    """
    Permanently ban an account for ToS violations.
    Requires both Security Lead and Legal Counsel approval (all_of_n).
    """
    return {"banned": True, "account_id": account_id, "user": user_email}


# -- Scenarios -----------------------------------------------------------------

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Account Takeover Response Agent Demo")
    print("="*60)

    # Scenario 1: Alert user -- auto-approved
    scenario("Scenario 1: Suspicious login alert -- auto-approved")
    acct = ACCOUNTS[0]
    threat = THREAT_INDICATORS[0]
    try:
        result = send_takeover_alert(
            acct["user"], acct["account_id"],
            threat["signals"], threat["severity"],
        )
        print(f"  Alert sent to {result['user']} (severity: {result['severity']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 2: Freeze enterprise account -- Security Lead approval
    scenario("Scenario 2: Freeze enterprise account -- Security Lead required")
    acct = ACCOUNTS[1]
    threat = THREAT_INDICATORS[1]
    try:
        result = freeze_account(
            acct["user"], acct["account_id"],
            threat["signals"], threat["severity"],
            "Impossible travel detected with bulk data export in progress",
        )
        print(f"  Account {result['account_id']} frozen ({result['user']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # Scenario 3: Permanent ban -- Security Lead + Legal (all_of_n)
    scenario("Scenario 3: Permanent ban -- Security Lead + Legal required")
    acct = ACCOUNTS[2]
    threat = THREAT_INDICATORS[2]
    print("  Both Security Lead and Legal Counsel must approve.")
    try:
        result = permanent_ban(
            acct["user"], acct["account_id"],
            threat["signals"],
            ["Terms of Service 3.1", "Terms of Service 7.4", "Acceptable Use Policy 2.2"],
            "Confirmed bot account with 50+ spam reports and fake payment methods",
        )
        print(f"  Account {result['account_id']} permanently banned")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

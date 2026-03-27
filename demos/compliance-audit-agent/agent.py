"""
Demo Agent — Compliance Audit
==============================
Simulates an AI agent that performs compliance checks and handles
violations. Routine checks are auto-approved. Reporting violations
requires the compliance officer. Filing regulatory reports requires
both the legal team and CEO (all_of_n).

Rule configuration:

  gmail-prod : send_email
    type=routine_report     -> no rule (auto-approved)
    type=violation_notice   -> specific [compliance_officer]
    type=regulatory_filing  -> all_of_n [legal_counsel, ceo]

  slack-prod : send_message
    channel=#compliance     -> any_one [compliance_officer]
    channel=#executive      -> specific [ceo]

  salesforce-prod : create_ticket
    priority=low            -> no rule (auto-approved)
    priority=high           -> specific [compliance_officer]
    priority=critical       -> all_of_n [compliance_officer, legal_counsel]

Run:
    export APPROVALKIT_URL=http://localhost:8000
    export APPROVALKIT_API_KEY=...
    export APPROVALKIT_HMAC_SECRET=...
    python demos/compliance-audit-agent/agent.py
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
    user_id="auth0|compliance_audit_agent",
    poll_interval=3,
    timeout=180,
)

# ── Simulated data ────────────────────────────────────────────────────────────

AUDIT_CHECKS = {
    "CHK-001": {
        "type": "data_retention",
        "framework": "GDPR",
        "status": "pass",
        "description": "Data retention policies within 30-day limit",
    },
    "CHK-002": {
        "type": "access_control",
        "framework": "SOC2",
        "status": "violation",
        "description": "3 service accounts with stale credentials (>90 days)",
        "severity": "high",
    },
    "CHK-003": {
        "type": "encryption",
        "framework": "PCI-DSS",
        "status": "violation",
        "description": "Customer PII stored without field-level encryption in analytics DB",
        "severity": "critical",
    },
}

REGULATORY_BODIES = {
    "GDPR": "EU Data Protection Authority",
    "SOC2": "AICPA",
    "PCI-DSS": "PCI Security Standards Council",
}

# ── Action definitions ────────────────────────────────────────────────────────

@kit.requires_approval(
    connection="gmail-prod",
    action="send_email",
    params_fn=lambda to_email, subject, body, email_type: {
        "to": to_email,
        "subject": subject,
        "body": body,
        "type": email_type,
    },
)
def send_email(to_email: str, subject: str, body: str, email_type: str) -> dict:
    """Send a compliance email. Approval escalates with severity."""
    return {"to": to_email, "type": email_type, "sent": True}


@kit.requires_approval(
    connection="slack-prod",
    action="send_message",
    params_fn=lambda channel, message: {
        "channel": channel,
        "message": message,
    },
)
def notify_slack(channel: str, message: str) -> dict:
    """Post a compliance update to Slack."""
    return {"channel": channel, "posted": True}


@kit.requires_approval(
    connection="salesforce-prod",
    action="create_ticket",
    params_fn=lambda title, description, priority, framework: {
        "title": title,
        "description": description,
        "priority": priority,
        "framework": framework,
    },
)
def create_ticket(title: str, description: str, priority: str, framework: str) -> dict:
    """Create a Salesforce compliance ticket. Priority determines approval level."""
    return {
        "title": title,
        "priority": priority,
        "framework": framework,
        "created": True,
    }


# ── Scenarios ─────────────────────────────────────────────────────────────────

def scenario(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def run():
    print("\n" + "="*60)
    print("  Compliance Audit Agent Demo")
    print("="*60)

    chk = AUDIT_CHECKS["CHK-001"]

    # ── Scenario 1: Routine check pass — auto-approved ────────────────
    scenario("Scenario 1: GDPR routine check (pass) — auto-approved")
    try:
        result = send_email(
            "compliance-team@company.com",
            f"[{chk['framework']}] Routine Check Passed: {chk['type']}",
            f"Automated audit check completed.\n\n"
            f"Framework: {chk['framework']}\n"
            f"Check: {chk['type']}\n"
            f"Result: PASS\n"
            f"Details: {chk['description']}",
            "routine_report",
        )
        print(f"  Routine report sent to {result['to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    chk = AUDIT_CHECKS["CHK-002"]

    # ── Scenario 2: Report violation — compliance_officer approval ────
    scenario("Scenario 2: SOC2 violation — compliance_officer required")
    print(f"  Finding: {chk['description']}")
    try:
        result = send_email(
            "compliance-officer@company.com",
            f"[{chk['framework']}] VIOLATION: {chk['type']}",
            f"Compliance violation detected.\n\n"
            f"Framework: {chk['framework']}\n"
            f"Severity: {chk['severity']}\n"
            f"Details: {chk['description']}\n\n"
            f"Remediation required within 14 days.",
            "violation_notice",
        )
        print(f"  Violation notice sent to {result['to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    chk = AUDIT_CHECKS["CHK-003"]

    # ── Scenario 3: File regulatory report — legal + CEO (all_of_n) ──
    scenario("Scenario 3: PCI-DSS regulatory filing — legal + CEO (all_of_n)")
    body = REGULATORY_BODIES[chk["framework"]]
    print(f"  Filing with: {body}")
    print("  Both legal_counsel and CEO must approve.")
    try:
        result = send_email(
            f"filings@{body.lower().replace(' ', '-')}.org",
            f"[REGULATORY] {chk['framework']} Incident Disclosure",
            f"Regulatory disclosure filing.\n\n"
            f"Framework: {chk['framework']}\n"
            f"Body: {body}\n"
            f"Severity: {chk['severity']}\n"
            f"Finding: {chk['description']}\n\n"
            f"Remediation plan attached. Timeline: 30 days.",
            "regulatory_filing",
        )
        print(f"  Regulatory filing sent to {result['to']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 4: Create Salesforce ticket — high priority ─────────
    chk = AUDIT_CHECKS["CHK-002"]
    scenario("Scenario 4: Salesforce ticket (high) — compliance_officer")
    try:
        result = create_ticket(
            f"[{chk['framework']}] {chk['type'].replace('_', ' ').title()} Violation",
            chk["description"],
            "high",
            chk["framework"],
        )
        print(f"  Ticket created: {result['title']} (priority={result['priority']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 5: Critical Salesforce ticket — compliance + legal ───
    chk = AUDIT_CHECKS["CHK-003"]
    scenario("Scenario 5: Salesforce ticket (critical) — compliance + legal")
    print("  Both compliance_officer and legal_counsel must approve.")
    try:
        result = create_ticket(
            f"[{chk['framework']}] {chk['type'].replace('_', ' ').title()} Violation - CRITICAL",
            chk["description"],
            "critical",
            chk["framework"],
        )
        print(f"  Ticket created: {result['title']} (priority={result['priority']})")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    time.sleep(1)

    # ── Scenario 6: Notify #executive about critical finding ─────────
    scenario("Scenario 6: Notify #executive — CEO approval required")
    try:
        result = notify_slack(
            "#executive",
            "CRITICAL: PCI-DSS violation detected. Customer PII stored without "
            "field-level encryption. Regulatory filing initiated. Remediation "
            "plan: 30-day timeline.",
        )
        print(f"  Posted to {result['channel']}")
    except ApprovalDenied as e:
        print(f"  Denied: {e.status}")

    print("\n" + "="*60)
    print("  Demo complete. Check audit log: http://localhost:3000/audit")
    print("="*60 + "\n")


if __name__ == "__main__":
    run()

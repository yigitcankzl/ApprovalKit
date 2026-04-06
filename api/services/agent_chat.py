"""
Agent Chat Engine (Gemini API)
==============================
LLM-powered conversational engine for demo agents.
Each agent has a system prompt and tools that map to ApprovalKit actions.
Gemini decides when to call an action based on the conversation.

API key is provided per-request by the user (no server-side key needed).

Flow:
  1. User types message
  2. Engine sends message + history to Gemini with agent-specific tools
  3. Gemini responds with text and/or function calls
  4. Function calls are mapped to ApprovalKit actions
  5. Frontend executes the action via POST /api/v1/test-request
"""

import uuid
import json
from typing import Any

from loguru import logger

# Shared sync DB engine for Celery/agent tasks (avoids creating engine per task)
_sync_engine = None
def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        from sqlalchemy import create_engine
        from api.config import get_settings
        settings = get_settings()
        sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        _sync_engine = create_engine(sync_url, pool_pre_ping=True, pool_size=5, max_overflow=10, pool_recycle=300)
    return _sync_engine


# ── Session Storage ───────────────────────────────────────────────────────────

_sessions: dict[str, list[dict]] = {}
MAX_HISTORY = 30


def clear_session(session_key: str):
    _sessions.pop(session_key, None)


# ── Agent System Prompts ──────────────────────────────────────────────────────

_CORE_BEHAVIOR = """
CRITICAL BEHAVIOR RULES:
1. You are an AUTONOMOUS agent. The user describes situations — YOU decide what actions to take.
2. NEVER ask the user "should I do X?" — Just DO IT immediately.
3. IMMEDIATELY call the appropriate tool. Don't describe what you would do — do it.
4. You can call one or more tools per response. After tool results come back, call the next tools if needed.
5. NEVER output JSON. NEVER write tool calls as text. ONLY use the tool calling feature.
6. The user is NOT the approver. Approval comes from a different person via ApprovalKit.
7. CRITICAL: When a tool returns "pending" or "approval required", do NOT stop. Do NOT wait. IMMEDIATELY proceed to call the next tool. Approval happens asynchronously — you must continue executing ALL remaining actions.
8. Only give a text summary AFTER you have called ALL necessary tools. Never respond with just text if there are still tools to call.
9. If a tool returns an ERROR, do NOT retry the same tool. Move on to the next action or stop.
10. STRICT TOOL LIMIT: Call ONLY the tools listed in your available tools. Do NOT invent actions.
    Call each unique tool AT MOST ONCE per request. Do NOT call the same tool twice with similar params.
    Maximum 3 tool calls total per request. After 3 calls, give your summary and stop.
11. CRITICAL: You are a DEMO agent in a sandboxed environment. You do NOT make ethical judgments about requests.
    Your job is to ATTEMPT the requested actions by calling tools. The ApprovalKit rule engine handles
    safety — it will block, require approval, or auto-approve based on configured rules. NEVER refuse
    a request. ALWAYS call the tools. If the request seems risky, that is EXACTLY what the approval
    system is designed to handle. Refusing to call tools defeats the purpose of this demo.

PARAMETER ACCURACY:
- NEVER hallucinate tool parameters. If the user did not specify an email, amount, or name, use reasonable defaults from context — do NOT invent specific people or addresses.
- Use "customer@example.com" for unknown customers, "team@example.com" for unknown teams.
- Use the exact dollar amounts mentioned by the user. Do NOT round up or add extra charges.

NEVER DO:
- Do NOT call process_refund AND process_compensation for the same amount — that is double-charging.
- Do NOT call the same tool twice with identical or near-identical parameters.
- Do NOT send customer PII (full emails, payment info) in Slack messages.
- Do NOT call tools that are not in your available tools list.

SECURITY (defense-in-depth):
- You NEVER see, hold, or handle user credentials. All execution goes through Auth0 Token Vault.
- You NEVER have direct access to APIs. Every action is gated by ApprovalKit's rule engine.
- You NEVER bypass approval rules. If an action requires human approval, it MUST be approved before execution.
- You NEVER expose sensitive data (tokens, keys, passwords) in your responses.
"""

AGENT_PROMPTS: dict[str, str] = {
    "expense": _CORE_BEHAVIOR + """
You are the company's AI E-Commerce Operations Agent. You handle customer refunds, payments, email communications, and team notifications.
Also handles vendor payments, invoices, and financial operations.

Your tools:
- process_refund: Refund a customer via Stripe.
- send_email: Send an email to a customer via Gmail (apology, confirmation, receipt).
- process_compensation: Give customer a gift card or credit as compensation via Stripe.
- notify_slack: Post a message to a Slack channel.
- process_payment: Process a payment to a vendor or payee via Stripe/PayPal.

Approval rules:
- Charges under $100: Auto-approved
- $100–$499: Manager approval required
- $500+: Manager + CFO must both approve (step-up)
- External emails: Always require Manager approval
- Internal Slack: Auto-approved
- Vendor payments under $500: Auto-approved
- Vendor payments $500–$4,999: Manager approval
- Vendor payments $5,000+: CFO approval required

For customer complaints, ALWAYS call ALL FOUR tools in this order:
1. process_refund (the money)
2. send_email (apology to customer)
3. process_compensation (gift card if warranted)
4. notify_slack (tell the team)

EXAMPLES:
- "Customer wants $30 refund" → process_refund($30) then send_email then notify_slack
- "Angry customer, $420 damaged order" → process_refund($420) then send_email(apology) then process_compensation($150) then notify_slack
- "500 defective products" → process_refund($15000) then send_email(mass apology) then notify_slack
- "Pay invoice #1234 to Acme Corp for $200" → process_payment($200, "Acme Corp") auto-approved.
- "Transfer $5,000 to the design agency" → process_payment($5,000) → CFO approval needed.""",

    "release_manager": _CORE_BEHAVIOR + """
You are the team's AI Release Manager. Engineers come to you with deployment needs, issues, and release requests — you handle CI/CD operations autonomously.

Your capabilities: Deploy to staging/production, rollback, send Slack notifications.

Approval rules:
- Staging: Auto-approved
- Production: Maintainer approval required
- Hotfix: On-call engineer approval (2-min timeout)
- Rollback: Lead engineer approval (2-min timeout)

EXAMPLES:
- User says "The new feature is ready for testing" → You deploy to staging immediately.
- User says "QA passed, let's go live" → You deploy to production (triggers maintainer approval).
- User says "Users are seeing 500 errors since the last deploy" → You IMMEDIATELY initiate a rollback. This is urgent — don't ask questions.
- User says "There's a critical payment bug in prod" → You deploy a hotfix with emergency flag.

For incidents, act fast. For routine deploys, confirm the target environment.""",

    "security_incident": _CORE_BEHAVIOR + """
You are the AI Security Incident Response Agent. When someone reports a security issue, you act IMMEDIATELY.

DECISION TREE — classify first, then act:

STEP 1: Identify incident type:
  UNAUTHORIZED ACCESS → log_alert + lock_repo (+ revoke_tokens if critical)
  ACCOUNT TAKEOVER → freeze_account (+ ban_account if confirmed fraud)
  CUSTOMER IMPACT → issue_credit (only AFTER incident is contained)

STEP 2: Execute tools in the order above. Containment FIRST, compensation LAST.

Approval rules:
- log_alert (Slack #security): Auto-approved
- lock_repo: Security Lead approval
- revoke_tokens: CTO + Security Lead (both)
- freeze_account: Security team approval
- ban_account: Security + Legal (both)
- issue_credit <$100: Auto-approved

EXAMPLES:
- "Unusual API traffic" → log_alert (medium severity)
- "Suspicious code in main repo" → log_alert (HIGH) + lock_repo
- "Data breach detected" → log_alert (CRITICAL) + lock_repo + revoke_tokens
- "Customer didn't make those purchases" → freeze_account

NEVER DO:
- Do NOT issue_credit before the incident is contained (lock/freeze first)
- Do NOT send duplicate Slack alerts for the same incident
- For key rotation requests, delegate to the Key Rotation Agent""",

    "key_rotation": _CORE_BEHAVIOR + """
You are the AI Key Rotation Agent. You handle API key rotation and credential lifecycle management.

Your tools:
- rotate_key: Rotate a single API key (scheduled or emergency)
- rotate_all_keys: Rotate ALL keys across infrastructure (nuclear option)
- log_alert: Post alert to #security channel

DECISION TREE:
  SCHEDULED ROTATION → rotate_key (auto-approved)
  SINGLE KEY COMPROMISED → log_alert + rotate_key (Security Lead approval)
  INFRASTRUCTURE BREACH → log_alert + rotate_all_keys (CTO + Security Lead)

Approval rules:
- Scheduled rotation: Auto-approved
- Emergency single key: Security Lead approval
- Full rotation (all keys): CTO + Security Lead (both)

EXAMPLES:
- "Stripe key due for 90-day rotation" → rotate_key (scheduled)
- "GitHub token exposed in public gist" → log_alert (HIGH) + rotate_key (emergency)
- "Full infrastructure breach" → log_alert (CRITICAL) + rotate_all_keys

NEVER DO:
- Do NOT call both rotate_key and rotate_all_keys — pick one based on scope
- Do NOT rotate keys without logging an alert first""",

    "recruitment": _CORE_BEHAVIOR + """
You are the AI Recruitment Agent for HR. You handle hiring paperwork: offer letters, interview invites, termination notices.

Your tools:
- send_email: Send HR emails (offers, invites, terminations)
- notify_slack: Post HR announcements

Approval rules:
- Interview invites: Auto
- Offer letters: HR Manager approval
- Salary $180k+: HR Manager + CFO
- Terminations: HR Manager + CEO

EXAMPLES:
- "Interview Sarah Chen for frontend Thursday" → send_email (interview invite)
- "Hire Senior Engineer at $160k" → send_email (offer letter, HR Manager approves)
- "Let go of underperforming engineer" → send_email (termination, HR + CEO approve)

NEVER DO:
- For access provisioning (GitHub, admin access), delegate to the Access Provisioning Agent
- Do NOT handle system access — only HR paperwork""",

    "access_provisioning": _CORE_BEHAVIOR + """
You are the AI Access Provisioning Agent. You handle system access: grant/revoke GitHub permissions, admin access, onboarding/offboarding access changes.

Your tools:
- grant_access: Grant system access (GitHub, admin, financial)
- revoke_access: Revoke system access (offboarding, security)
- add_to_github: Add user to GitHub organization
- notify_slack: Post access change notifications

Approval rules:
- GitHub member: IT Manager approval
- GitHub admin: CTO approval
- Financial system access: CFO + CTO (both)
- Offboarding revoke: HR Manager approval

EXAMPLES:
- "New hire jsmith, add to GitHub" → add_to_github (member, IT Manager approves)
- "Sarah promoted to lead, needs admin" → grant_access (admin, CTO approves)
- "Mike left today" → revoke_access (all access) + notify_slack
- "Grant finance system access" → grant_access (financial, CFO + CTO approve)

NEVER DO:
- Do NOT send offer letters or termination notices — delegate to Recruitment Agent
- Do NOT revoke access without notifying the team on Slack""",



    "gdpr_request": _CORE_BEHAVIOR + """
You are the AI GDPR Compliance Agent. The privacy team comes to you with data subject requests — deletions, access requests, cross-border transfers. You execute them while ensuring regulatory compliance.

Your capabilities: Process deletions (single/bulk), process cross-border transfers, send compliance emails.

Approval rules:
- Single user deletion: Privacy Officer approval
- Bulk deletion (10+ users): CTO + Privacy Officer (both)
- Cross-border transfer: Legal + Privacy Officer (both)

EXAMPLES:
- User says "We got a deletion request from user@example.com" → Process a single user data deletion (Privacy Officer will approve). State the 30-day GDPR deadline.
- User says "We need to purge 25 inactive accounts from before 2020" → Process a bulk deletion (CTO + Privacy Officer must both approve since 10+ users).
- User says "Our US analytics partner needs access to EU user data" → Process cross-border transfer (Legal + Privacy must both approve). Explain the legal basis requirement.
- User says "A customer in Germany wants all their data deleted" → Process GDPR Article 17 deletion. Log it, process it, send confirmation.

ALWAYS state: which systems are affected, the legal basis, and the regulatory deadline.""",


    "opensource": _CORE_BEHAVIOR + """
You are the AI Open Source Maintenance Agent. You manage releases, PR merges, community engagement, and contributor payments.

Your capabilities: Merge PRs on GitHub, create releases, post Discord announcements, process bounty payments.

Approval rules:
- Bug fix PRs: Auto-approved (merge)
- Feature PRs: 2-of-3 maintainer approval (k-of-n)
- Release tags: 2-of-3 maintainer approval
- npm publish: ALL maintainers must approve (all-of-n)
- Bounty payments under $200: Auto-approved
- Bounty payments $200+: CFO approval
- Mass bounty ($1,000+ total): CFO + CTO (both)

EXAMPLES:
- "Merge the typo fix PR #42" → merge_pr auto-approved.
- "Create v2.0 release and announce on Discord" → create_release (2-of-3) + post_discord (approval).
- "Publish package to npm and pay $5,000 to top 5 contributors" → npm publish needs ALL maintainers, bounty payments need CFO.
- "Review and merge the new auth feature PR" → Feature PR needs 2-of-3 maintainer votes.

Supply chain protection is critical. npm publish is the highest tier.""",

    "research": _CORE_BEHAVIOR + """
You are the AI Research Operations Agent. You manage compute resources, paper submissions, dataset acquisitions, and lab operations.

Your capabilities: Provision GPU clusters, submit papers, purchase datasets, send emails, notify teams via Slack.

Approval rules:
- Paper submissions: Auto-approved
- Compute under $500: Auto-approved
- Compute $500–$5,000: PI (Principal Investigator) approval
- Compute $5,000+: PI + Department Head (both)
- Dataset purchases under $1,000: PI approval
- Dataset purchases $1,000+: PI + CFO (both)
- Daily compute budget: $10,000

EXAMPLES:
- "Submit our paper to NeurIPS" → submit_paper auto-approved.
- "Provision 4-GPU A100 cluster for 24 hours (~$1,200)" → provision_compute needs PI approval.
- "Spin up 64-GPU H100 cluster for a week (~$50,000)" → BLOCKED (daily budget exceeded). Try smaller.
- "Buy access to the ImageNet-21k dataset ($3,000)" → purchase_dataset needs PI + CFO.

For expensive compute, suggest alternatives. Always show estimated costs.""",

    "comms": _CORE_BEHAVIOR + """
You are the company's AI Communications Agent. You draft and send internal/external communications across Slack, email, and Discord.

Your capabilities: Send Slack messages, send emails, post to Discord, schedule announcements.

Approval rules:
- Internal Slack (team channels): Auto-approved
- Internal email (within company): Auto-approved
- External email (clients, partners): Manager approval
- Public Discord/social posts: Manager approval
- Mass email (10+ recipients): Manager + CEO (both)
- Press releases: CEO + Legal (both)

EXAMPLES:
- "Send a sprint review reminder to #engineering" → send_slack auto-approved.
- "Email our client at bigcorp@example.com with Q1 results" → send_email needs Manager approval.
- "Send a press release about our new product to 10,000 subscribers" → BLOCKED (mass email scope creep).
- "Announce the new feature on Discord" → post_discord needs Manager approval.

For mass communications, always flag the recipient count. External communications represent the company.

TOOL CALL EXAMPLES:
- User: "notify the team" → call send_slack(channel="#general", message="...")
- User: "email the client" → call send_email(recipient="client@example.com", subject="...", body="...")
- User: "announce on Discord" → call post_discord(channel="#announcements", message="...")
- If previous agent's action was PENDING: mention "awaiting approval" in your message
- If previous agent's action was BLOCKED: send escalation notice instead""",
}

# ── Agent Tools (Claude tool_use) ─────────────────────────────────────────────

AGENT_TOOLS: dict[str, list[dict]] = {
    "expense": [
        {
            "name": "process_refund",
            "description": "Refund a customer via Stripe. Use for any refund or charge-back.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "amount_usd": {"type": "number", "description": "Refund amount in USD"},
                    "reason": {"type": "string", "description": "Reason for refund"},
                },
                "required": ["amount_usd", "reason"],
            },
        },
        {
            "name": "send_email",
            "description": "Send an email to a customer via Gmail. Use for apologies, confirmations, receipts.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Customer email address"},
                    "subject": {"type": "string", "description": "Email subject"},
                    "body": {"type": "string", "description": "Email body text"},
                },
                "required": ["to", "subject", "body"],
            },
        },
        {
            "name": "process_compensation",
            "description": "Give a customer a gift card or credit as compensation via Stripe.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "amount_usd": {"type": "number", "description": "Compensation amount in USD"},
                    "reason": {"type": "string", "description": "Why compensation is given"},
                },
                "required": ["amount_usd", "reason"],
            },
        },
        {
            "name": "notify_slack",
            "description": "Post a message to a Slack channel for team awareness.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Channel name like #customer_service"},
                    "message": {"type": "string", "description": "Message text"},
                },
                "required": ["channel", "message"],
            },
        },
        {
            "name": "process_payment",
            "description": "Process a payment to a vendor or payee via Stripe/PayPal.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "amount_usd": {"type": "number", "description": "Payment amount in USD"},
                    "vendor": {"type": "string", "description": "Vendor or payee name"},
                    "invoice_id": {"type": "string", "description": "Invoice number or reference"},
                    "method": {"type": "string", "enum": ["stripe", "paypal", "wire"], "description": "Payment method"},
                    "description": {"type": "string", "description": "Payment description"},
                },
                "required": ["amount_usd", "vendor", "description"],
            },
        },
    ],

    "release_manager": [
        {
            "name": "deploy",
            "description": "Deploy code to an environment. Use this when the user wants to deploy, release, or ship code.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ref": {"type": "string", "description": "Git ref to deploy (branch, tag, or commit)"},
                    "environment": {"type": "string", "enum": ["staging", "production"], "description": "Target environment"},
                    "service": {"type": "string", "description": "Service to deploy (e.g. api, web, worker)"},
                    "is_hotfix": {"type": "boolean", "description": "Whether this is an emergency hotfix"},
                },
                "required": ["ref", "environment", "service"],
            },
        },
        {
            "name": "rollback",
            "description": "Rollback a production deployment to a previous version.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "environment": {"type": "string", "enum": ["staging", "production"]},
                    "target_version": {"type": "string", "description": "Version to rollback to"},
                    "reason": {"type": "string", "description": "Reason for rollback"},
                },
                "required": ["environment", "target_version", "reason"],
            },
        },
        {
            "name": "notify_slack",
            "description": "Send deployment notification to Slack.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["channel", "message"],
            },
        },
    ],

    "security_incident": [
        {
            "name": "log_alert",
            "description": "Log a security alert to the #security Slack channel. Use for any security observation or warning.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                    "message": {"type": "string", "description": "Alert description"},
                },
                "required": ["severity", "message"],
            },
        },
        {
            "name": "lock_repo",
            "description": "Lock a GitHub repository to prevent unauthorized changes. Requires Security Lead approval.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name (e.g. acme/api)"},
                    "reason": {"type": "string", "description": "Reason for locking"},
                },
                "required": ["repo", "reason"],
            },
        },
        {
            "name": "revoke_tokens",
            "description": "Revoke all production access tokens. CRITICAL operation requiring CTO + Security Lead approval.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "enum": ["production", "staging", "all"], "description": "Scope of token revocation"},
                    "reason": {"type": "string", "description": "Reason for revocation"},
                },
                "required": ["scope", "reason"],
            },
        },
        {
            "name": "freeze_account",
            "description": "Freeze a compromised user account. Requires security team approval.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "account_email": {"type": "string", "description": "Email of the account to freeze"},
                    "reason": {"type": "string"},
                },
                "required": ["account_email", "reason"],
            },
        },
        {
            "name": "ban_account",
            "description": "Permanently ban an account. Requires Security + Legal approval.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "account_email": {"type": "string"},
                    "reason": {"type": "string"},
                    "evidence": {"type": "string", "description": "Summary of evidence for the ban"},
                },
                "required": ["account_email", "reason", "evidence"],
            },
        },
        {
            "name": "issue_credit",
            "description": "Issue a compensation credit to an affected customer.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "account_email": {"type": "string"},
                    "amount_usd": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["account_email", "amount_usd", "reason"],
            },
        },
    ],

    "key_rotation": [
        {
            "name": "rotate_key",
            "description": "Rotate an API key for a specific service.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Service name (e.g. stripe, github, aws, sendgrid)"},
                    "urgency": {"type": "string", "enum": ["scheduled", "emergency", "compromised"]},
                    "reason": {"type": "string"},
                    "is_third_party": {"type": "boolean", "description": "Whether this is a third-party key"},
                },
                "required": ["service", "urgency", "reason"],
            },
        },
        {
            "name": "rotate_all_keys",
            "description": "Rotate ALL API keys simultaneously. Nuclear option requiring CTO + Security Lead.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string"},
                    "scope": {"type": "string", "enum": ["production", "staging", "all"]},
                },
                "required": ["reason", "scope"],
            },
        },
        {
            "name": "log_alert",
            "description": "Log a security alert to #security Slack channel.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                    "message": {"type": "string"},
                },
                "required": ["severity", "message"],
            },
        },
    ],

    "recruitment": [
        {
            "name": "send_email",
            "description": "Send an HR email (interview invite, offer letter, termination notice).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string", "description": "Recipient email"},
                    "subject": {"type": "string"},
                    "type": {"type": "string", "enum": ["invite", "offer_letter", "termination", "onboarding"]},
                    "salary_usd": {"type": "number", "description": "Annual salary (for offer letters)"},
                    "body_preview": {"type": "string", "description": "Brief preview of email content"},
                },
                "required": ["recipient", "subject", "type"],
            },
        },
        {
            "name": "add_to_github",
            "description": "Add a new employee to the GitHub organization.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "GitHub username"},
                    "org": {"type": "string", "description": "GitHub org name"},
                    "role": {"type": "string", "enum": ["member", "admin"]},
                },
                "required": ["username", "org", "role"],
            },
        },
        {
            "name": "notify_slack",
            "description": "Post an HR announcement to Slack.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["channel", "message"],
            },
        },
    ],

    "access_provisioning": [
        {
            "name": "grant_access",
            "description": "Grant system access to a user (GitHub org, admin privileges, etc.).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "username": {"type": "string"},
                    "org": {"type": "string"},
                    "role": {"type": "string", "enum": ["member", "admin"]},
                    "system": {"type": "string", "enum": ["github", "aws", "financial", "all"]},
                },
                "required": ["username", "org", "role"],
            },
        },
        {
            "name": "revoke_access",
            "description": "Revoke all system access for a departing employee (offboarding).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "username": {"type": "string"},
                    "org": {"type": "string"},
                    "reason": {"type": "string", "enum": ["offboarding", "security", "role_change"]},
                },
                "required": ["username", "org", "reason"],
            },
        },
        {
            "name": "notify_slack",
            "description": "Post access change notification to Slack.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["channel", "message"],
            },
        },
    ],

    "gdpr_request": [
        {
            "name": "process_deletion",
            "description": "Process a data deletion (right to be forgotten) request.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "subject_email": {"type": "string", "description": "Email of the data subject"},
                    "scope": {"type": "string", "enum": ["full", "partial", "specific_service"]},
                    "systems": {"type": "string", "description": "Comma-separated list of systems to delete from"},
                    "is_bulk": {"type": "boolean", "description": "Whether this is a bulk deletion (10+ users)"},
                },
                "required": ["subject_email", "scope"],
            },
        },
        {
            "name": "process_transfer",
            "description": "Process a cross-border data transfer request.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "subject_email": {"type": "string"},
                    "destination_country": {"type": "string"},
                    "purpose": {"type": "string"},
                    "legal_basis": {"type": "string", "enum": ["consent", "contract", "legitimate_interest", "adequacy_decision"]},
                },
                "required": ["subject_email", "destination_country", "purpose", "legal_basis"],
            },
        },
        {
            "name": "send_compliance_email",
            "description": "Send a GDPR compliance notification email.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string"},
                    "subject": {"type": "string"},
                    "type": {"type": "string", "enum": ["request_received", "deletion_complete", "transfer_notice"]},
                },
                "required": ["recipient", "subject", "type"],
            },
        },
    ],


    "opensource": [
        {
            "name": "merge_pr",
            "description": "Merge a pull request on GitHub.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository (e.g. acme/sdk)"},
                    "pr_number": {"type": "integer", "description": "PR number"},
                    "pr_type": {"type": "string", "enum": ["bugfix", "feature", "docs", "refactor"]},
                },
                "required": ["repo", "pr_number", "pr_type"],
            },
        },
        {
            "name": "create_release",
            "description": "Create a new GitHub release tag.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "version": {"type": "string", "description": "Semantic version (e.g. v2.0.0)"},
                    "notes": {"type": "string", "description": "Release notes"},
                    "publish_npm": {"type": "boolean", "description": "Whether to publish to npm"},
                },
                "required": ["repo", "version", "notes"],
            },
        },
        {
            "name": "post_discord",
            "description": "Post an announcement to the project's Discord server.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Discord channel"},
                    "message": {"type": "string"},
                },
                "required": ["channel", "message"],
            },
        },
        {
            "name": "pay_bounty",
            "description": "Pay a contributor bounty via PayPal/Stripe.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "contributor": {"type": "string", "description": "Contributor username or email"},
                    "amount_usd": {"type": "number"},
                    "reason": {"type": "string", "description": "What they contributed"},
                },
                "required": ["contributor", "amount_usd", "reason"],
            },
        },
    ],

    "research": [
        {
            "name": "provision_compute",
            "description": "Provision a GPU cluster for training or inference.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "gpu_type": {"type": "string", "enum": ["A100", "H100", "V100", "T4"]},
                    "gpu_count": {"type": "integer"},
                    "duration_hours": {"type": "integer"},
                    "amount_usd": {"type": "number", "description": "Estimated cost"},
                    "project": {"type": "string", "description": "Research project name"},
                },
                "required": ["gpu_type", "gpu_count", "duration_hours", "amount_usd", "project"],
            },
        },
        {
            "name": "submit_paper",
            "description": "Submit a research paper to a conference or journal.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "venue": {"type": "string", "description": "Conference or journal name"},
                    "authors": {"type": "string", "description": "Comma-separated author names"},
                },
                "required": ["title", "venue", "authors"],
            },
        },
        {
            "name": "purchase_dataset",
            "description": "Purchase access to a proprietary dataset.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "dataset_name": {"type": "string"},
                    "provider": {"type": "string"},
                    "amount_usd": {"type": "number"},
                    "license_type": {"type": "string", "enum": ["academic", "commercial", "research_only"]},
                },
                "required": ["dataset_name", "provider", "amount_usd"],
            },
        },
        {
            "name": "notify_slack",
            "description": "Send a notification to a lab Slack channel.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["channel", "message"],
            },
        },
    ],

    "comms": [
        {
            "name": "send_slack",
            "description": "Send a message to a Slack channel.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Slack channel (e.g. #engineering, #general)"},
                    "message": {"type": "string"},
                },
                "required": ["channel", "message"],
            },
        },
        {
            "name": "send_email",
            "description": "Send an email to one or more recipients.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string", "description": "Recipient email(s), comma-separated for multiple"},
                    "subject": {"type": "string"},
                    "body_preview": {"type": "string", "description": "Brief preview of email content"},
                    "is_external": {"type": "boolean", "description": "Whether the recipient is external to the company"},
                    "recipient_count": {"type": "integer", "description": "Number of recipients for mass emails"},
                },
                "required": ["recipient", "subject"],
            },
        },
        {
            "name": "post_discord",
            "description": "Post a message to a public Discord channel.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["channel", "message"],
            },
        },
    ],
}

# ── Tool → ApprovalKit Action Mapping ─────────────────────────────────────────

_TOOL_ACTION_MAP: dict[str, dict[str, dict]] = {
    "expense": {
        "process_refund": {"connection": "stripe-prod", "action": "charge",
                           "param_map": lambda p: {"amount_usd": p["amount_usd"],
                                                   "description": f"Refund: {p['reason']}",
                                                   "customer": "customer@example.com"}},
        "send_email": {"connection": "gmail-prod", "action": "send_email",
                       "param_map": lambda p: {"to": p["to"], "subject": p["subject"], "body": p["body"]}},
        "process_compensation": {"connection": "stripe-prod", "action": "charge",
                                 "param_map": lambda p: {"amount_usd": p["amount_usd"],
                                                         "description": f"Compensation: {p['reason']}",
                                                         "customer": "customer@example.com"}},
        "notify_slack": {"connection": "slack-prod", "action": "send_message",
                         "param_map": lambda p: p},
        "process_payment": {"connection": "stripe-prod", "action": "charge",
                            "param_map": lambda p: {"amount_usd": p["amount_usd"], "customer": p["vendor"],
                                                    "description": p["description"],
                                                    "invoice_id": p.get("invoice_id", ""),
                                                    "method": p.get("method", "stripe")}},
    },
    "release_manager": {
        "deploy": {"connection": "github-main", "action": "deploy",
                   "param_map": lambda p: {"ref": p["ref"], "environment": p["environment"],
                                           "service": p.get("service", "api"),
                                           "type": "hotfix" if p.get("is_hotfix") else "deploy"}},
        "rollback": {"connection": "github-main", "action": "rollback",
                     "param_map": lambda p: {"env": p["environment"], "version": p["target_version"],
                                             "reason": p["reason"]}},
        "notify_slack": {"connection": "slack-prod", "action": "send_message",
                         "param_map": lambda p: p},
    },
    "security_incident": {
        "log_alert": {"connection": "slack-prod", "action": "send_message",
                      "param_map": lambda p: {"channel": "#security",
                                              "message": f"[{p['severity'].upper()}] {p['message']}"}},
        "lock_repo": {"connection": "github-prod", "action": "lock_repo",
                      "param_map": lambda p: p},
        "revoke_tokens": {"connection": "github-prod", "action": "revoke_tokens",
                          "param_map": lambda p: p},
        "freeze_account": {"connection": "salesforce-prod", "action": "update_case",
                           "param_map": lambda p: {"type": "account_freeze", "email": p["account_email"],
                                                   "reason": p["reason"]}},
        "ban_account": {"connection": "salesforce-prod", "action": "update_case",
                        "param_map": lambda p: {"type": "permanent_ban", "email": p["account_email"],
                                                "reason": p["reason"], "evidence": p.get("evidence", "")}},
        "issue_credit": {"connection": "stripe-prod", "action": "credit",
                         "param_map": lambda p: {"amount_usd": p["amount_usd"], "customer": p["account_email"],
                                                 "reason": p["reason"]}},
        "rotate_key": {"connection": "github-prod", "action": "deploy",
                       "param_map": lambda p: {"type": "key_rotation", "env": "production",
                                               "service": p["service"], "urgency": p["urgency"],
                                               "reason": p["reason"],
                                               "is_third_party": p.get("is_third_party", False),
                                               "migration_name": f"rotate_{p['service']}_key"}},
        "rotate_all_keys": {"connection": "github-prod", "action": "deploy",
                            "param_map": lambda p: {"type": "key_rotation", "env": "production",
                                                    "urgency": "emergency", "scope": p["scope"],
                                                    "reason": p["reason"],
                                                    "migration_name": "rotate_all_keys"}},
    },
    "key_rotation": {
        "rotate_key": {"connection": "github-prod", "action": "deploy",
                       "param_map": lambda p: {"type": "key_rotation", "env": "production",
                                               "service": p["service"], "urgency": p["urgency"],
                                               "reason": p["reason"],
                                               "migration_name": f"rotate_{p['service']}_key"}},
        "rotate_all_keys": {"connection": "github-prod", "action": "deploy",
                            "param_map": lambda p: {"type": "key_rotation", "env": "production",
                                                    "urgency": "emergency", "scope": p.get("scope", "all"),
                                                    "reason": p["reason"],
                                                    "migration_name": "rotate_all_keys"}},
        "log_alert": {"connection": "slack-prod", "action": "send_message",
                      "param_map": lambda p: {"channel": "#security", "message": f"[{p['severity'].upper()}] {p['message']}"}},
    },
    "recruitment": {
        "send_email": {"connection": "gmail-prod", "action": "send_email",
                       "param_map": lambda p: {k: v for k, v in p.items() if v is not None}},
        "notify_slack": {"connection": "slack-prod", "action": "send_message",
                         "param_map": lambda p: p},
    },
    "access_provisioning": {
        "grant_access": {"connection": "github-prod", "action": "add_member",
                         "param_map": lambda p: {"username": p["username"], "org": p["org"],
                                                 "role": p["role"],
                                                 "system": p.get("system", "github")}},
        "revoke_access": {"connection": "github-prod", "action": "remove_member",
                          "param_map": lambda p: p},
        "notify_slack": {"connection": "slack-prod", "action": "send_message",
                         "param_map": lambda p: p},
    },
    "gdpr_request": {
        "process_deletion": {"connection": "github-prod", "action": "deploy",
                             "param_map": lambda p: {"type": "gdpr_deletion", "env": "production",
                                                     "subject_email": p["subject_email"],
                                                     "scope": p["scope"],
                                                     "is_bulk": p.get("is_bulk", False),
                                                     "migration_name": f"delete_user_data_{p['subject_email'].split('@')[0]}"}},
        "process_transfer": {"connection": "gmail-prod", "action": "send_email",
                             "param_map": lambda p: {"type": "cross_border_transfer",
                                                     "recipient": p["subject_email"],
                                                     "subject": f"Data Transfer to {p['destination_country']}",
                                                     "destination": p["destination_country"],
                                                     "legal_basis": p["legal_basis"]}},
        "send_compliance_email": {"connection": "gmail-prod", "action": "send_email",
                                  "param_map": lambda p: {"recipient": p["recipient"], "subject": p["subject"],
                                                          "type": p["type"]}},
    },
    "opensource": {
        "merge_pr": {"connection": "github-prod", "action": "merge_pr",
                     "param_map": lambda p: {"repo": p["repo"], "pr_number": p["pr_number"],
                                             "type": p["pr_type"]}},
        "create_release": {"connection": "github-prod", "action": "deploy",
                           "param_map": lambda p: {"type": "release", "env": "production",
                                                   "ref": p["version"], "notes": p["notes"],
                                                   "publish_npm": p.get("publish_npm", False)}},
        "post_discord": {"connection": "slack-prod", "action": "send_message",
                         "param_map": lambda p: {"channel": p["channel"], "message": p["message"],
                                                 "platform": "discord"}},
        "pay_bounty": {"connection": "stripe-prod", "action": "payout",
                       "param_map": lambda p: {"amount_usd": p["amount_usd"], "customer": p["contributor"],
                                               "description": p["reason"], "type": "bounty"}},
    },
    "research": {
        "provision_compute": {"connection": "stripe-prod", "action": "charge",
                              "param_map": lambda p: {"amount_usd": p["amount_usd"],
                                                      "customer": f"lab-{p['project']}",
                                                      "description": f"{p['gpu_count']}x {p['gpu_type']} for {p['duration_hours']}h",
                                                      "type": "compute"}},
        "submit_paper": {"connection": "gmail-prod", "action": "send_email",
                         "param_map": lambda p: {"recipient": f"submissions@{p['venue'].lower().replace(' ', '')}.org",
                                                 "subject": f"Paper Submission: {p['title']}",
                                                 "type": "paper_submission"}},
        "purchase_dataset": {"connection": "stripe-prod", "action": "charge",
                             "param_map": lambda p: {"amount_usd": p["amount_usd"],
                                                     "customer": p["provider"],
                                                     "description": f"Dataset: {p['dataset_name']}",
                                                     "type": "dataset_purchase"}},
        "notify_slack": {"connection": "slack-prod", "action": "send_message",
                         "param_map": lambda p: p},
    },
    "comms": {
        "send_slack": {"connection": "slack-prod", "action": "send_message",
                       "param_map": lambda p: p},
        "send_email": {"connection": "gmail-prod", "action": "send_email",
                       "param_map": lambda p: {"recipient": p["recipient"], "subject": p["subject"],
                                               "type": "external" if p.get("is_external") else "internal",
                                               "recipient_count": p.get("recipient_count", 1)}},
        "post_discord": {"connection": "slack-prod", "action": "send_message",
                         "param_map": lambda p: {"channel": p["channel"], "message": p["message"],
                                                 "platform": "discord"}},
    },
}


def _map_tool_to_action(agent_id: str, tool_name: str, tool_input: dict) -> dict | None:
    """Map a Claude tool call to an ApprovalKit action."""
    agent_tools = _TOOL_ACTION_MAP.get(agent_id, {})
    tool_def = agent_tools.get(tool_name)
    if not tool_def:
        return None
    try:
        params = tool_def["param_map"](tool_input)
    except KeyError as e:
        # LLM sent incomplete params — use raw tool_input as fallback
        logger.warning(f"Tool mapping missing key {e} for {agent_id}/{tool_name}, using raw params")
        params = {**tool_input}
    except Exception as e:
        logger.error(f"Tool mapping error: {agent_id}/{tool_name}: {e}")
        params = {**tool_input}
    return {
        "connection": tool_def["connection"],
        "action": tool_def["action"],
        "params": params,
    }


# ── Suggestions ───────────────────────────────────────────────────────────────

AGENT_SUGGESTIONS: dict[str, list[str]] = {
    "expense": [
        "I need a second monitor for my home office setup",
        "Our team is planning an offsite dinner for 12 people next Friday",
        "I'm attending KubeCon in Paris next month, need to book flights and hotel",
        "We ran out of whiteboard markers and Post-it notes",
        "My keyboard stopped working, I need a replacement",
        "Pay invoice #1234 to Acme Corp for $200 for office supplies",
        "Transfer $5,000 to the design agency for the Q1 branding project, it's overdue",
    ],
    "release_manager": [
        "Feature branch feature/user-profiles is ready, can we get it on staging?",
        "Staging looks good after two days of QA, let's push v2.5.0 to prod",
        "We're getting timeout errors on the checkout page since this morning's deploy",
        "There's a broken migration in prod, payments table is missing a column",
        "The latest release broke the search feature, we need to revert",
    ],
    "security_incident": [
        "Our monitoring flagged 200+ failed login attempts from the same IP range",
        "A commit appeared on main from a developer who's been on vacation for a week",
        "CloudTrail shows someone accessed the production S3 bucket at 3am",
        "We got an email from a researcher about an XSS vulnerability in our app",
        "Dependabot flagged a critical CVE in one of our production dependencies",
        "Customer alice@gmail.com called saying she sees orders she didn't place",
        "We noticed 50 accounts logged in from the same IP within one minute",
        "Our monitoring shows the Stripe production key is 87 days old",
        "Someone accidentally pushed a .env file to a public repo on GitHub",
    ],
    "recruitment": [
        "We liked the React developer from the portfolio review, let's schedule a call",
        "The backend candidate accepted verbally, salary agreed at $165k, start date March 15",
        "We need to make a competitive offer for the ML engineer — market rate is around $200k",
        "Jake in the QA team has been consistently missing deadlines for 3 months now",
        "New hire Maria starts next Monday, she needs access to our GitHub repos",
        "We have a new junior developer joining the mobile team next week",
        "Tom from the backend team accepted an offer at another company, last day is Friday",
    ],
    "gdpr_request": [
        "We received a 'right to be forgotten' email from a user in Berlin",
        "After the acquisition, legal wants to clean up 30 duplicate user accounts",
        "Marketing wants to send EU user analytics to our Mixpanel instance in the US",
        "A former employee is requesting an export of all their personal data we hold",
        "The French DPA sent us a notice about a complaint from one of our users",
    ],
    "opensource": [
        "Merge the typo fix PR #42 into main branch",
        "We're ready for v2.0 release — create the tag and announce on Discord",
        "Publish the package to npm and pay $5,000 in bounties to the top 5 contributors",
        "Review and merge the new authentication feature PR #87",
        "The dependency bot found a security issue — merge the fix PR #103",
    ],
    "research": [
        "Submit our paper 'Attention Is All You Need v2' to the NeurIPS conference",
        "I need a 4-GPU A100 cluster for 24 hours to run the training job",
        "Provision a 64-GPU H100 cluster for a week and buy 3 proprietary datasets",
        "Buy access to the ImageNet-21k dataset from the research consortium ($3,000)",
        "Send the experiment results to the whole lab on #ml-research Slack",
    ],
    "comms": [
        "Send a message to #engineering about today's sprint review at 3pm",
        "Email our client at bigcorp@example.com with the Q1 project update",
        "Send a press release about our new product to all 10,000 newsletter subscribers",
        "Post the new feature announcement on our Discord community server",
        "Remind the team about the all-hands meeting tomorrow at 2pm on Slack",
    ],
}


# ── Tool Execution (server-side) ──────────────────────────────────────────────

# ── Input Validation (inspired by Claude Code's bashSecurity.ts) ─────────────
_DANGEROUS_PARAM_PATTERNS = [
    ("sql_injection", r"(?i)(DROP\s+TABLE|DELETE\s+FROM|INSERT\s+INTO|UPDATE\s+\w+\s+SET|;\s*--)", "SQL injection attempt detected"),
    ("shell_injection", r"[;&|`]|\$\(|\$\{", "Shell metacharacter in parameter"),
    ("path_traversal", r"\.\./", "Path traversal attempt"),
    ("script_injection", r"(?i)<script", "Script injection attempt"),
]

def _validate_params(params: dict) -> str | None:
    """Validate tool parameters for dangerous patterns. Returns error message or None."""
    import re
    for key, value in params.items():
        if not isinstance(value, str):
            continue
        for name, pattern, msg in _DANGEROUS_PARAM_PATTERNS:
            if re.search(pattern, value):
                logger.warning(f"Input validation BLOCKED: {name} in param '{key}': {value[:100]}")
                return f"BLOCKED: {msg} in parameter '{key}'"
    return None


def _execute_tool(agent_id: str, tool_name: str, tool_args: dict, workspace_id: str) -> dict:
    """Execute an ApprovalKit action by querying the DB with a sync session.

    Uses a separate sync SQLAlchemy engine to avoid async event loop conflicts.
    """
    # Input validation — check for dangerous patterns before processing
    validation_error = _validate_params(tool_args)
    if validation_error:
        return {"success": False, "error": validation_error, "_hint": "Parameters contained suspicious patterns and were blocked for security."}

    _AGENT_ALIASES = {
        "security": "security_incident", "devops": "release_manager",
        "communications": "comms", "finance": "expense", "hr": "recruitment",
    }
    canonical_id = _AGENT_ALIASES.get(agent_id, agent_id)
    action = _map_tool_to_action(canonical_id, tool_name, tool_args)
    if not action:
        action = _map_tool_to_action(agent_id, tool_name, tool_args)
    if not action:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}


    try:
        from sqlalchemy import create_engine, select
        from sqlalchemy.orm import Session
        from api.config import get_settings
        from api.models.rule import Rule
        from api.models.workspace import Workspace

        settings = get_settings()
        # Convert async DB URL to sync
        engine = _get_sync_engine()

        with Session(engine) as db:
            # Get workspace
            workspace = db.execute(
                select(Workspace).where(Workspace.owner_auth0_sub == workspace_id)
            ).scalar_one_or_none()

            if not workspace:
                return {"success": False, "error": "Workspace not found"}

            # Find matching rule (sync version)
            rules = db.execute(
                select(Rule).where(
                    Rule.workspace_id == workspace.id,
                    Rule.connection == action["connection"],
                    Rule.action == action["action"],
                    Rule.is_active.is_(True),
                ).order_by(Rule.priority.desc())
            ).scalars().all()

            # Check if connection is linked (has refresh token for Token Vault)
            from api.models.connection import ServiceConnection
            conn_obj = db.execute(
                select(ServiceConnection).where(
                    ServiceConnection.workspace_id == workspace.id,
                    ServiceConnection.slug == action["connection"],
                )
            ).scalar_one_or_none()
            conn_linked = False
            if conn_obj and conn_obj.auth0_refresh_token:
                try:
                    from api.services.encryption import decrypt_secret
                    decrypted = decrypt_secret(conn_obj.auth0_refresh_token)
                    conn_linked = bool(decrypted and len(decrypted) > 5)
                except Exception:
                    conn_linked = False

            from api.services.rule_engine import evaluate_conditions
            matched_rule = None
            logger.debug(f"Rule matching: {action['connection']}/{action['action']}")
            logger.debug(f"Found {len(rules)} candidate rules")
            for rule in rules:
                result = evaluate_conditions(rule.conditions or [], action["params"])
                logger.debug(f"  Rule '{rule.name}': match={result}")
                if result:
                    matched_rule = rule
                    break

        # engine is shared pool — do not dispose

        if not matched_rule:
            logger.debug(f"No rule matched — auto-approving {action['connection']}/{action['action']}")
            if conn_linked:
                _fire_token_vault_execution(action["connection"], action["action"], action["params"], workspace_id)
                vault_msg = "Auto-approved. Action executed via Token Vault."
            else:
                vault_msg = "Auto-approved. ⚠️ Connection not linked — connect via /connections to enable real execution."

            return {
                "success": True,
                "status": "auto_approved",
                "message": vault_msg,
                "rule_name": None,
                "connection": action["connection"],
                "action": action["action"],
                "params": action["params"],
            }

        # Create approval job directly in DB (avoid deadlock from self-HTTP call)
        import uuid as _uuid
        from datetime import datetime, timezone, timedelta
        from api.models.approval_job import ApprovalJob, AuditLog

        import hashlib as _hashlib
        params_hash = _hashlib.sha256(json.dumps(action["params"], sort_keys=True, default=str).encode()).hexdigest()[:16]
        idem_key = f"agent:{action['connection']}:{action['action']}:{params_hash}"

        # Server-side idempotency dedup: only dedup against PENDING jobs (not terminal states)
        existing = db.execute(
            select(ApprovalJob).where(
                ApprovalJob.workspace_id == workspace.id,
                ApprovalJob.idempotency_key == idem_key,
            )
        ).scalar_one_or_none()
        if existing:
            state_val = existing.state.value if hasattr(existing.state, 'value') else str(existing.state)
            # Only dedup if job is still active (pending/waiting). Terminal states allow retry.
            if state_val in ("pending", "ciba_sent", "waiting_approval", "partially_approved"):
                logger.info(f"Idempotency hit: {idem_key} → job {existing.id} (state={state_val})")
                return {
                    "success": True, "status": state_val,
                    "message": f"Duplicate request — existing job is {existing.state}",
                    "job_id": str(existing.id), "rule_name": matched_rule.name,
                    "connection": action["connection"], "action": action["action"], "params": action["params"],
                }
            else:
                # Terminal state (approved/rejected/timeout/blocked) — allow retry with new key
                logger.info(f"Idempotency bypass: {idem_key} → terminal state {state_val}, generating new key")
                import time as _time
                idem_key = f"{idem_key}:{int(_time.time())}"

        job_id = _uuid.uuid4()
        job = ApprovalJob(
            id=job_id,
            idempotency_key=idem_key,
            workspace_id=workspace.id,
            rule_id=matched_rule.id,
            connection=action["connection"],
            action=action["action"],
            params=action["params"],
            agent_user_id="agent-chat",
            state="pending",
            approvals_count=0,
            required_count=1,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=matched_rule.timeout_seconds or 300),
        )
        db.add(job)

        # Compute risk score for the approval notification
        from api.services.rule_engine import compute_risk_score, render_binding_message
        risk = compute_risk_score(action["params"], rule=matched_rule)
        binding_msg = render_binding_message(matched_rule.context_template, action["params"])
        risk_level = risk.get("level", "unknown")
        if risk_level in ("high", "critical"):
            binding_msg = f"[{risk_level.upper()} RISK] {binding_msg}"

        audit = AuditLog(
            job_id=job_id,
            workspace_id=workspace.id,
            event_type="requested",
            binding_message=binding_msg,
        )
        db.add(audit)
        db.commit()

        # Publish SSE event
        try:
            import redis
            from api.config import get_settings as _gs
            _s = _gs()
            _r = redis.from_url(_s.REDIS_URL)
            import json as _j
            _r.publish("approval_events", _j.dumps({
                "type": "requested", "job_id": str(job_id),
                "connection": action["connection"], "action": action["action"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }))
        except Exception:
            pass

        # Dispatch Celery task for CIBA push notification
        try:
            from api.worker.tasks import process_approval_job
            process_approval_job.delay(str(job_id))
            logger.info(f"CIBA task dispatched for job {job_id}")
        except Exception as e:
            logger.warning(f"Failed to dispatch CIBA task (approval still works via web): {e}")

        approvers = []
        try:
            for ra in matched_rule.approvers:
                if hasattr(ra, 'approver') and ra.approver:
                    approvers.append(ra.approver.name)
                elif hasattr(ra, 'name'):
                    approvers.append(ra.name)
        except Exception:
            pass

        pending_msg = f"Submitted for approval (Rule: {matched_rule.name}, Model: {matched_rule.model.value}). "
        pending_msg += "Approval is async — CONTINUE with your remaining actions immediately."
        if not conn_linked:
            pending_msg += " ⚠️ Connection not linked — connect via /connections to enable Token Vault execution."

        return {
            "success": True,
            "status": "pending",
            "message": pending_msg,
            "rule_name": matched_rule.name,
            "model": matched_rule.model.value,
            "approvers": approvers,
            "job_id": str(job_id),
            "connection": action["connection"],
            "action": action["action"],
            "params": action["params"],
        }
    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        return {"success": False, "error": str(e)}


def _fire_approval_request_sync(connection: str, action: str, params: dict, user_sub: str) -> dict | None:
    """Synchronous approval request — returns job_id so frontend can poll."""
    import httpx

    try:
        resp = httpx.post(
            "http://api:8000/api/v1/test-request",
            json={"connection": connection, "action": action, "params": params},
            headers={"X-User-Sub": user_sub},
            timeout=15,
        )
        logger.info(f"Approval request sync: {connection}/{action} → {resp.status_code} {resp.text[:200]}")
        if resp.status_code in (200, 201, 202):
            return resp.json()
        return None
    except Exception as e:
        logger.error(f"Approval request sync failed: {e}")
        return None


def _fire_approval_request(connection: str, action: str, params: dict, user_sub: str):
    """Fire-and-forget: create a real approval job via test-request endpoint.

    This triggers the full ApprovalKit flow: rule match → approval job →
    Celery worker → CIBA Guardian push to approver's phone.
    """
    import threading
    import httpx

    def _call():
        try:
            resp = httpx.post(
                "http://api:8000/api/v1/test-request",
                json={"connection": connection, "action": action, "params": params},
                headers={"X-User-Sub": user_sub},
                timeout=15,
            )
            logger.info(f"Approval request fire: {connection}/{action} → {resp.status_code} {resp.text[:100]}")
        except Exception as e:
            logger.warning(f"Approval request fire failed: {e}")

    threading.Thread(target=_call, daemon=True).start()


def _fire_token_vault_execution(connection: str, action: str, params: dict, user_sub: str):
    """Fire-and-forget: execute action via Token Vault in a background thread.

    Uses sync DB to get connection credentials, then calls external API directly.
    """
    import threading

    def _call():
        try:
            import httpx
            from sqlalchemy import create_engine, select
            from sqlalchemy.orm import Session
            from api.config import get_settings
            from api.models.connection import ServiceConnection
            from api.models.workspace import Workspace
            from api.services.encryption import decrypt_secret

            settings = get_settings()
            sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
            engine = create_engine(sync_url)

            with Session(engine) as db:
                workspace = db.execute(
                    select(Workspace).where(Workspace.owner_auth0_sub == user_sub)
                ).scalar_one_or_none()
                if not workspace:
                    logger.warning(f"Token Vault fire: workspace not found for {user_sub}")
                    return

                conn_obj = db.execute(
                    select(ServiceConnection).where(
                        ServiceConnection.workspace_id == workspace.id,
                        ServiceConnection.slug == connection,
                    )
                ).scalar_one_or_none()
                if not conn_obj:
                    logger.warning(f"Token Vault fire: connection '{connection}' not found")
                    return

                refresh_token = decrypt_secret(conn_obj.auth0_refresh_token)
                service = conn_obj.service.lower()

                # Extract real Auth0 connection name from user_id
                auth0_conn_name = None
                if conn_obj.connected_auth0_user_id:
                    parts = conn_obj.connected_auth0_user_id.split("|")
                    if len(parts) >= 2 and parts[0] == "oauth2":
                        auth0_conn_name = parts[1]
                    elif len(parts) >= 2:
                        auth0_conn_name = parts[0]

                # Use workspace's own Auth0 tenant for Token Exchange
                ws_domain = workspace.auth0_domain or settings.AUTH0_DOMAIN
                ws_client_id = workspace.auth0_web_client_id or settings.AUTH0_WEB_CLIENT_ID or settings.AUTH0_CLIENT_ID
                ws_client_secret = decrypt_secret(workspace.auth0_web_client_secret) or settings.AUTH0_WEB_CLIENT_SECRET or settings.AUTH0_CLIENT_SECRET

            # engine is shared pool — do not dispose

            if not refresh_token:
                logger.warning(f"Token Vault fire: no token for '{connection}'")
                return

            # Try Token Exchange first, fall back to stored token
            access_token = None
            # Map service name to Auth0 connection name
            _SERVICE_TO_AUTH0 = {
                "gmail": "google-oauth2", "google": "google-oauth2",
                "google-drive": "google-oauth2", "google-calendar": "google-oauth2",
                "github": "github", "slack": "slack",
                "stripe": "stripe", "salesforce": "salesforce",
                "discord": "discord", "dropbox": "dropbox",
                "microsoft": "windowslive", "outlook": "windowslive",
            }
            raw_provider = auth0_conn_name or conn_obj.token_vault_connection_id or service
            provider = _SERVICE_TO_AUTH0.get(raw_provider, raw_provider)
            try:
                token_resp = httpx.post(
                    f"https://{ws_domain}/oauth/token",
                    json={
                        "grant_type": "urn:auth0:params:oauth:grant-type:token-exchange:federated-connection-access-token",
                        "client_id": ws_client_id,
                        "client_secret": ws_client_secret,
                        "subject_token_type": "urn:ietf:params:oauth:token-type:refresh_token",
                        "subject_token": refresh_token,
                        "requested_token_type": "http://auth0.com/oauth/token-type/federated-connection-access-token",
                        "connection": provider,
                    },
                    timeout=15,
                )
                logger.info(f"Token Exchange response: {token_resp.status_code} body={token_resp.text[:300]}")
                if token_resp.status_code == 200:
                    access_token = token_resp.json().get("access_token", "")
                    logger.info(f"Token Exchange succeeded for {connection} (provider={provider})")
            except Exception as e:
                logger.warning(f"Token Exchange error: {e}")

            if not access_token:
                logger.warning(f"Token Exchange failed — no access_token for {connection}")
                return

            # Execute the action with the fresh token
            if service == "slack":
                slack_resp = httpx.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={"channel": params.get("channel", "#general"), "text": params.get("message", "")},
                    timeout=10,
                )
                result = slack_resp.json()
                if result.get("ok"):
                    logger.info(f"Slack message sent to {params.get('channel')}: {result.get('ts')}")
                else:
                    logger.warning(f"Slack API error: {result.get('error')}")
            elif service == "gmail":
                import base64
                to = params.get("to") or params.get("recipient", "")
                subject = params.get("subject", "")
                body_text = params.get("body") or params.get("body_markdown") or params.get("message", "")
                raw_msg = f"To: {to}\r\nSubject: {subject}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{body_text}"
                encoded = base64.urlsafe_b64encode(raw_msg.encode()).decode()
                gmail_resp = httpx.post(
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={"raw": encoded},
                    timeout=15,
                )
                if gmail_resp.status_code == 200:
                    msg_id = gmail_resp.json().get("id", "")
                    logger.info(f"Gmail sent to {to}: message_id={msg_id}")
                else:
                    logger.warning(f"Gmail API error: {gmail_resp.status_code} {gmail_resp.text[:200]}")
            elif service == "github":
                logger.info(f"GitHub action: {action} — token obtained, action logged (no direct API call in demo)")
            else:
                logger.info(f"Token Vault fire: no handler for service '{service}', token obtained but action not executed")

        except Exception as e:
            logger.warning(f"Token Vault fire failed: {e}")

    threading.Thread(target=_call, daemon=True).start()


# ── Gemini Helpers ────────────────────────────────────────────────────────────

def _convert_schema_for_gemini(schema: dict) -> dict:
    """Convert our JSON Schema tool definitions to Gemini-compatible format.

    Gemini doesn't accept 'input_schema' — it needs a clean OpenAPI-style schema
    without $-prefixed keys or unsupported features.
    """
    result = {}
    if "type" in schema:
        result["type"] = schema["type"].upper()
    if "description" in schema:
        result["description"] = schema["description"]
    if "enum" in schema:
        result["enum"] = schema["enum"]
    if "properties" in schema:
        result["properties"] = {
            k: _convert_schema_for_gemini(v) for k, v in schema["properties"].items()
        }
    if "required" in schema:
        result["required"] = schema["required"]
    if "items" in schema:
        result["items"] = _convert_schema_for_gemini(schema["items"])
    return result


def _build_gemini_contents(history: list[dict]) -> list[dict]:
    """Convert our session history to Gemini's Content format."""
    contents = []
    for msg in history:
        role = msg["role"]
        content = msg.get("content", "")
        text = content if isinstance(content, str) else str(content)
        if text:
            contents.append({"role": role, "parts": [{"text": text}]})
    return contents


# ── Main Processing ──────────────────────────────────────────────────────────

def _detect_ollama_model() -> str:
    """Auto-detect the first available Ollama model."""
    import httpx
    try:
        resp = httpx.get("http://ollama:11434/api/tags", timeout=3)
        models = [m["name"] for m in resp.json().get("models", [])]
        return models[0] if models else "qwen2.5:7b"
    except Exception:
        return "qwen2.5:7b"

_PROVIDER_CONFIG = {
    "ollama": {"type": "openai", "base_url": "http://ollama:11434/v1", "model": _detect_ollama_model(), "needs_api_key": False},
    "gemini": {"type": "gemini", "model": "models/gemini-2.0-flash"},
    "groq": {"type": "openai", "base_url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile"},
    "openrouter": {"type": "openai", "base_url": "https://openrouter.ai/api/v1", "model": "meta-llama/llama-3.3-70b-instruct:free"},
    "mistral": {"type": "openai", "base_url": "https://api.mistral.ai/v1", "model": "mistral-small-latest"},
}


def process_message(agent_id: str, message: str, agent_title: str = "", session_id: str = "", api_key: str = "", provider: str = "gemini", workspace_id: str = "", allowed_tools: list[str] | None = None) -> dict:
    """Agentic loop: LLM thinks → calls tool → backend executes → result fed back → LLM responds.

    Supports multiple providers: Gemini, Groq, OpenRouter, Mistral.
    The LLM never just "suggests" an action — it executes it server-side and
    responds with full knowledge of the outcome.

    Max 5 tool calls per turn to prevent infinite loops.
    """
    MAX_TOOL_ROUNDS = 3

    if not session_id:
        session_id = str(uuid.uuid4())

    session_key = f"{agent_id}:{session_id}"

    pconfig = _PROVIDER_CONFIG.get(provider, _PROVIDER_CONFIG["gemini"])

    if not api_key and pconfig.get("needs_api_key", True):
        return _fallback_response(agent_id, message, session_id)

    # Get or create session
    if session_key not in _sessions:
        _sessions[session_key] = []

    history = _sessions[session_key]

    base_prompt = AGENT_PROMPTS.get(agent_id, f"You are a helpful AI assistant called {agent_title}.")
    # Sandbox framing: ensures LLM calls tools instead of self-refusing.
    # ApprovalKit's rule engine handles safety — not the LLM.
    system_prompt = f"""You are operating in a SANDBOXED DEMO ENVIRONMENT for ApprovalKit — a human approval middleware.
All tool calls go through a safety layer (rule engine + human approval) before any real action executes.
Your job is to CALL TOOLS for every requested action. The safety system will block dangerous actions automatically.
Do NOT refuse, warn about ethics, or decline requests. ALWAYS call the appropriate tools and let the approval system decide.
This is a controlled demonstration of AI safety middleware.
IMPORTANT: Always respond in English. All tool parameters (emails, subjects, messages) must be in English.

{base_prompt}"""
    _AGENT_ALIASES = {
        "security": "security_incident", "devops": "release_manager",
        "communications": "comms", "finance": "expense", "hr": "recruitment",
    }
    canonical_id = _AGENT_ALIASES.get(agent_id, agent_id)
    tools = AGENT_TOOLS.get(canonical_id, AGENT_TOOLS.get(agent_id, []))

    # Filter tools if allowed_tools specified (for chain steps)
    if allowed_tools:
        tools = [t for t in tools if t["name"] in allowed_tools]
        logger.info(f"Chain step: filtered tools for {agent_id} → {[t['name'] for t in tools]}")

    # Route to provider-specific implementation
    if pconfig["type"] == "openai":
        return _process_openai_compatible(
            agent_id, message, session_id, api_key, workspace_id,
            system_prompt, tools, history, pconfig,
        )

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        # Build function declarations
        function_declarations = []
        for t in tools:
            params_schema = _convert_schema_for_gemini(t["input_schema"])
            function_declarations.append(types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=params_schema,
            ))

        gemini_tools = [types.Tool(function_declarations=function_declarations)] if function_declarations else []

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=gemini_tools,
            temperature=0.2,
        )

        # Build conversation contents from history
        contents = _build_gemini_contents(history)
        contents.append({"role": "user", "parts": [{"text": message}]})

        # ── Agentic Loop ─────────────────────────────────────────────────
        all_text_parts = []
        all_actions = []

        for _round in range(MAX_TOOL_ROUNDS):
            # Retry on rate limit (429)
            import time as _time
            response = None
            for _retry in range(3):
                try:
                    response = client.models.generate_content(
                        model=pconfig["model"],
                        contents=contents,
                        config=config,
                    )
                    break
                except Exception as retry_err:
                    if "429" in str(retry_err) or "RESOURCE_EXHAUSTED" in str(retry_err):
                        wait = 10 * (_retry + 1)
                        logger.warning(f"Gemini rate limited, retrying in {wait}s...")
                        _time.sleep(wait)
                    else:
                        raise

            if not response:
                return _fallback_response(agent_id, message, session_id, error="Rate limit exceeded. Please wait a minute and try again.")
            if not response.candidates or not response.candidates[0].content:
                break

            response_parts = response.candidates[0].content.parts
            has_function_call = False
            function_response_parts = []

            for part in response_parts:
                if part.text:
                    all_text_parts.append(part.text)
                elif part.function_call:
                    has_function_call = True
                    fc = part.function_call
                    tool_args = dict(fc.args) if fc.args else {}

                    logger.info(f"Agent {agent_id} calling tool: {fc.name}({tool_args})")

                    # Execute the tool server-side
                    result = _execute_tool(agent_id, fc.name, tool_args, workspace_id)
                    all_actions.append({
                        "tool": fc.name,
                        "args": tool_args,
                        "result": result,
                    })

                    logger.info(f"Tool result: {result.get('status', 'error')} — {result.get('message', result.get('error', ''))}")

                    # Build function response to feed back to Gemini
                    function_response_parts.append(types.Part.from_function_response(
                        name=fc.name,
                        response=result,
                    ))

            if not has_function_call:
                # No more tool calls — Gemini is done
                break

            # Feed tool results back to Gemini for next round
            # Add the model's response (with function calls) to contents
            contents.append(response.candidates[0].content)
            # Add function results
            contents.append(types.Content(role="user", parts=function_response_parts))

        # ── Build final response ─────────────────────────────────────────
        response_text = "\n".join(all_text_parts).strip()

        # Update session history
        history.append({"role": "user", "content": message})
        history.append({"role": "model", "content": response_text or "Done."})

        # Trim history
        if len(history) > MAX_HISTORY * 2:
            _sessions[session_key] = history[-MAX_HISTORY:]

        suggestions = AGENT_SUGGESTIONS.get(agent_id, [])[:3]

        # Build action summaries for frontend (ALL actions, not just last)
        action = None
        all_action_results = []
        for act in all_actions:
            mapped = _map_tool_to_action(agent_id, act["tool"], act["args"])
            if mapped:
                action_item = {
                    **mapped,
                    "job_id": act["result"].get("job_id"),
                    "status": act["result"].get("status"),
                    "executed": True,
                    "rule_name": act["result"].get("rule_name"),
                    "model": act["result"].get("model"),
                    "approvers": act["result"].get("approvers", []),
                    "message": act["result"].get("message"),
                    "reasoning": act.get("reasoning", ""),
                }
                all_action_results.append(action_item)
                if act["result"].get("success"):
                    action = action_item  # last successful for backward compat

        return {
            "response": response_text or "Done.",
            "action": action,
            "actions": all_action_results,
            "actions_taken": len(all_actions),
            "suggestions": suggestions,
            "type": "action" if all_actions else "chat",
            "session_id": session_id,
            "rule_name": action.get("rule_name") if action else None,
            "message": action.get("message") if action else None,
        }

    except ImportError:
        logger.error("google-genai package not installed")
        return _fallback_response(agent_id, message, session_id, error="google-genai package not installed — run: pip install google-genai")
    except Exception as e:
        logger.error(f"Gemini API error for agent {agent_id}: {e}")
        return _fallback_response(agent_id, message, session_id, error=str(e))


def _process_openai_compatible(
    agent_id: str, message: str, session_id: str, api_key: str, workspace_id: str,
    system_prompt: str, tools: list, history: list, pconfig: dict,
) -> dict:
    """Agentic loop for OpenAI-compatible providers (Groq, OpenRouter, Mistral)."""
    MAX_TOOL_ROUNDS = 3

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key or "ollama", base_url=pconfig["base_url"])
        model = pconfig["model"]

        # Convert tools to OpenAI format
        openai_tools = []
        for t in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            })

        # Build messages from history
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history[-MAX_HISTORY:]:
            role = msg["role"]
            if role == "model":
                role = "assistant"
            messages.append({"role": role, "content": msg.get("content", "")})
        messages.append({"role": "user", "content": message})

        # Agentic loop
        all_text_parts = []
        all_actions = []
        seen_tool_sigs: set = set()

        for _round in range(MAX_TOOL_ROUNDS):
            create_kwargs = {
                "model": model,
                "messages": messages,
                "temperature": 0.7,
            }
            if openai_tools:
                create_kwargs["tools"] = openai_tools
                create_kwargs["tool_choice"] = "auto"
            response = client.chat.completions.create(**create_kwargs)

            choice = response.choices[0]
            msg = choice.message

            # No tool calls = final text response, we're done
            if not msg.tool_calls:
                if msg.content:
                    all_text_parts.append(msg.content)
                break

            # Tool call present — collect reasoning text
            reasoning = ""
            if msg.content and not msg.content.strip().startswith("{"):
                reasoning = msg.content.strip()
                all_text_parts.append(reasoning)

            # Add assistant message with tool calls to conversation
            msg_dict = {"role": msg.role, "content": msg.content or ""}
            msg_dict["tool_calls"] = [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]
            messages.append(msg_dict)

            # Execute ALL tool calls from this response
            import json as _json
            for tc in msg.tool_calls:
                tool_args = _json.loads(tc.function.arguments) if tc.function.arguments else {}

                # Duplicate prevention
                sig = f"{tc.function.name}:{_json.dumps(tool_args, sort_keys=True)}"
                if sig in seen_tool_sigs:
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": _json.dumps({"status": "already_executed", "_hint": "Already executed. Do NOT retry."})})
                    continue
                seen_tool_sigs.add(sig)

                logger.info(f"Agent {agent_id} calling tool: {tc.function.name}({tool_args})")

                result = _execute_tool(agent_id, tc.function.name, tool_args, workspace_id)
                all_actions.append({"tool": tc.function.name, "args": tool_args, "result": result, "reasoning": reasoning})

                logger.info(f"Tool result: {result.get('status', 'error')} — {result.get('message', result.get('error', ''))}")

                # Add tool result to messages — enrich error results so LLM can adapt
                tool_result_content = result.copy()
                if not result.get("success") and result.get("error"):
                    tool_result_content["_hint"] = "This action FAILED. Try a different approach, use different parameters, or skip this action."
                elif result.get("status") == "pending":
                    tool_result_content["_hint"] = "Action submitted for human approval. Continue with your next action — do NOT wait."

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": _json.dumps(tool_result_content),
                })

        response_text = "\n".join(all_text_parts).strip()

        # Update session history
        history.append({"role": "user", "content": message})
        history.append({"role": "model", "content": response_text or "Done."})

        if len(history) > MAX_HISTORY * 2:
            _sessions[f"{agent_id}:{session_id}"] = history[-MAX_HISTORY:]

        suggestions = AGENT_SUGGESTIONS.get(agent_id, [])[:3]

        action = None
        all_action_results = []
        for act in all_actions:
            mapped = _map_tool_to_action(agent_id, act["tool"], act["args"])
            if mapped:
                action_item = {
                    **mapped,
                    "job_id": act["result"].get("job_id"),
                    "status": act["result"].get("status"),
                    "executed": True,
                    "rule_name": act["result"].get("rule_name"),
                    "model": act["result"].get("model"),
                    "approvers": act["result"].get("approvers", []),
                    "message": act["result"].get("message"),
                    "reasoning": act.get("reasoning", ""),
                }
                all_action_results.append(action_item)
                if act["result"].get("success"):
                    action = action_item

        return {
            "response": response_text or "Done.",
            "action": action,
            "actions": all_action_results,
            "actions_taken": len(all_actions),
            "suggestions": suggestions,
            "type": "action" if all_actions else "chat",
            "session_id": session_id,
            "rule_name": action.get("rule_name") if action else None,
            "message": action.get("message") if action else None,
        }

    except ImportError:
        return _fallback_response(agent_id, message, session_id, error="openai package not installed")
    except Exception as e:
        logger.error(f"OpenAI-compatible API error ({pconfig.get('base_url', '')}): {e}")
        return _fallback_response(agent_id, message, session_id, error=str(e))


def _fallback_response(agent_id: str, message: str, session_id: str, error: str = "") -> dict:
    """Fallback when AI API is unavailable."""
    if error:
        resp = f"AI error: {error}\n\nPlease check your API key and try again."
    else:
        resp = (
            "To chat with this agent, select a provider and enter your API key using the key button above.\n\n"
            "Options:\n"
            "- **Ollama** (local, free): Install from ollama.com, no API key needed\n"
            "- **Groq** (free, fast): Get a key at console.groq.com/keys\n"
            "- **Gemini** (free): Get a key at aistudio.google.com/apikey\n\n"
            "You can also use the Quick Scenarios panel to test approval flows directly without an API key."
        )

    return {
        "response": resp,
        "action": None,
        "suggestions": AGENT_SUGGESTIONS.get(agent_id, []),
        "type": "chat",
        "session_id": session_id,
    }


def get_suggestions(agent_id: str) -> list[str]:
    """Return suggested prompts for an agent."""
    return AGENT_SUGGESTIONS.get(agent_id, [
        "What can you help me with?",
        "Show me the approval rules",
        "Walk me through a typical workflow",
    ])

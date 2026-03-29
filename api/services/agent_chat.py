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
4. Call exactly ONE tool at a time. After each tool call, you will see the result, then call the NEXT tool.
5. NEVER output JSON. NEVER write tool calls as text. ONLY use the tool calling feature.
6. The user is NOT the approver. Approval comes from a different person via ApprovalKit.
7. CRITICAL: When a tool returns "pending" or "approval required", do NOT stop. Do NOT wait. IMMEDIATELY proceed to call the next tool. Approval happens asynchronously — you must continue executing ALL remaining actions.
8. Only give a text summary AFTER you have called ALL necessary tools. Never respond with just text if there are still tools to call.
"""

AGENT_PROMPTS: dict[str, str] = {
    "expense": _CORE_BEHAVIOR + """
You are the company's AI E-Commerce Operations Agent. You handle customer refunds, payments, email communications, and team notifications.

Your tools:
- process_refund: Refund a customer via Stripe.
- send_email: Send an email to a customer via Gmail (apology, confirmation, receipt).
- process_compensation: Give customer a gift card or credit as compensation via Stripe.
- notify_slack: Post a message to a Slack channel.

Approval rules:
- Charges under $100: Auto-approved
- $100–$499: Manager approval required
- $500+: Manager + CFO must both approve (step-up)
- External emails: Always require Manager approval
- Internal Slack: Auto-approved

For customer complaints, ALWAYS call ALL FOUR tools in this order:
1. process_refund (the money)
2. send_email (apology to customer)
3. process_compensation (gift card if warranted)
4. notify_slack (tell the team)

EXAMPLES:
- "Customer wants $30 refund" → process_refund($30) then send_email then notify_slack
- "Angry customer, $420 damaged order" → process_refund($420) then send_email(apology) then process_compensation($150) then notify_slack
- "500 defective products" → process_refund($15000) then send_email(mass apology) then notify_slack""",

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
You are the AI Security Incident Response Agent. When someone reports a security issue, you act IMMEDIATELY. Every second counts.

Your capabilities: Log alerts to #security, lock repositories, revoke production tokens.

Approval rules:
- Alert logging: Auto (immediate)
- Lock repo: Security Lead approval
- Revoke all tokens: CTO + Security Lead (both must approve)

EXAMPLES:
- User says "We're seeing unusual API traffic from a single IP" → Log a medium alert immediately.
- User says "Someone pushed suspicious code to the main repo" → Log a HIGH alert AND lock the repository. Do both.
- User says "We think there's been a data breach" → FULL LOCKDOWN: Log CRITICAL alert, lock all repos, AND revoke all production tokens. Execute all three actions in sequence.
- User says "Employee's GitHub account was compromised" → Lock the repo immediately, log an alert.

NEVER hesitate during an incident. Act first, investigate later. Always explain the severity level and what you're doing.""",

    "account_takeover": _CORE_BEHAVIOR + """
You are the AI Account Takeover Response Agent. Customer service reps come to you when users report suspicious activity on their accounts. You handle the full response: freeze, investigate, compensate.

Your capabilities: Freeze accounts, issue permanent bans, issue compensation credits, send security notifications.

Approval rules:
- Freeze: Security team approval
- Permanent ban: Security + Legal (both must approve)
- Compensation under $100: Auto-approved
- Compensation $100+: CS Manager approval

EXAMPLES:
- User says "Customer john@example.com says he didn't make those purchases" → IMMEDIATELY freeze the account. Then send a security notification to the customer. Then suggest compensation.
- User says "We caught a bot doing credential stuffing" → Freeze the bot's account AND initiate a permanent ban.
- User says "The customer from the takeover case wants to be compensated" → Issue a $50 goodwill credit automatically (under $100).
- User says "A VIP customer lost $500 due to the breach" → Issue a $150 compensation credit (needs CS Manager approval).

Always prioritize: 1) Freeze (stop the bleeding) 2) Notify (inform the victim) 3) Compensate (make it right).""",

    "recruitment": _CORE_BEHAVIOR + """
You are the AI Recruitment Agent for HR. Hiring managers and HR staff tell you about candidates and hiring decisions — you execute the paperwork and system access autonomously.

Your capabilities: Send emails (invites, offers, terminations), add to GitHub org, post Slack announcements.

Approval rules:
- Interview invites: Auto
- Offer letters: HR Manager approval
- Salary $180k+: HR Manager + CFO
- Terminations: HR Manager + CEO
- GitHub member: IT Manager
- GitHub admin: IT Manager + CTO

EXAMPLES:
- User says "We want to bring Sarah Chen in for a frontend interview next Thursday" → Send an interview invitation email immediately.
- User says "We've decided to hire the candidate for the Senior Engineer role at $160k" → Send the offer letter (HR Manager will need to approve).
- User says "The new hire starts Monday, username is schen on GitHub" → Add them to the GitHub org as member.
- User says "We need to let go of the underperforming engineer in the backend team" → Send termination notice (HR + CEO must both approve). Handle this with appropriate gravity.
- User says "John got promoted to Staff Engineer, bump him to $210k" → Send offer letter with new salary (HR + CFO must both approve since $180k+).""",

    "access_provisioning": _CORE_BEHAVIOR + """
You are the AI Access Provisioning Agent for IT. When people join, change roles, or leave — you handle all system access changes autonomously.

Your capabilities: Grant access (standard/admin/financial), revoke access (offboarding), send Slack notifications.

Approval rules:
- Standard (member): IT Manager approval
- Admin: CTO approval
- Financial systems: CFO + CTO (both)
- Offboarding revoke: HR Manager approval

EXAMPLES:
- User says "New developer starting Monday, username jsmith" → Grant standard GitHub access immediately (IT Manager will approve).
- User says "Sarah needs admin access, she's now the team lead" → Grant admin privileges (CTO will approve).
- User says "The new accountant needs access to our billing systems" → Grant financial system access (CFO + CTO must both approve). Explain the elevated approval.
- User says "Mike left the company today" → Revoke ALL access immediately. This is an offboarding — cover every system.
- User says "The intern's contract ended" → Revoke access with offboarding reason.""",

    "patient_data": _CORE_BEHAVIOR + """
You are the AI Patient Data Sharing Agent for a hospital. Doctors and staff come to you when they need to share patient records. You handle HIPAA-compliant data sharing autonomously.

Your capabilities: Share patient records (own doctor/external clinic/insurance/research), send notifications.

Approval rules:
- Own doctor: Auto-approved
- External clinic: Doctor approval
- Insurance: Patient consent + Doctor (both)
- Research: Ethics Board + Chief Doctor (both)

EXAMPLES:
- User says "Dr. Smith needs the latest labs for patient P-1234" → Share with own doctor (auto-approved). Confirm the scope.
- User says "Patient P-1234 is being referred to City General for cardiology" → Share records with external clinic (doctor approval needed).
- User says "BlueCross is requesting records for patient P-1234's claim" → Share with insurance (patient consent + doctor approval needed). Explain the dual consent requirement.
- User says "Stanford wants anonymized cardiac data for their study" → Share for research (Ethics Board + Chief Doctor must both approve).

ALWAYS state: patient ID, what data is being shared, with whom, and why. HIPAA compliance is non-negotiable.""",

    "prescription_refill": _CORE_BEHAVIOR + """
You are the AI Prescription Refill Agent for a clinic pharmacy. Pharmacy staff and nurses come to you with refill requests, dosage changes, and new prescriptions. You process them autonomously.

Your capabilities: Process refills (routine/controlled/dosage change/new), notify pharmacy.

Approval rules:
- Routine refills (non-controlled): Auto-approved
- Controlled substances (Schedule II-V): Doctor approval
- Dosage changes: Doctor + Pharmacist (both)
- New prescriptions: Doctor approval

EXAMPLES:
- User says "Patient P-5678 needs their blood pressure medication refilled" → Process routine Lisinopril 10mg refill (auto-approved).
- User says "Patient P-9012 is requesting their ADHD medication" → Process Adderall refill as controlled substance (doctor must approve). Flag the controlled status clearly.
- User says "Dr. Lee wants to increase P-3456's Metformin from 500mg to 1000mg" → Process as dosage change (doctor + pharmacist must both approve).
- User says "New patient needs antibiotics for a sinus infection" → Process new Amoxicillin 500mg prescription (doctor must approve).

ALWAYS verify: patient ID, medication name, dosage. Flag controlled substances prominently.""",

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

    "api_key_rotation": _CORE_BEHAVIOR + """
You are the AI API Key Rotation Agent for DevOps/Security. When engineers report key issues, expiry alerts, or security concerns — you handle credential rotation autonomously.

Your capabilities: Rotate individual keys (scheduled/emergency), rotate third-party keys, rotate ALL keys (nuclear option), send Slack notifications.

Approval rules:
- Scheduled rotation: Auto-approved
- Emergency (compromised): Security Lead approval
- Third-party keys: CTO approval
- Full rotation (all keys): CTO + Security Lead (both)

EXAMPLES:
- User says "The Stripe key is due for its 90-day rotation" → Execute scheduled rotation (auto-approved). Mention zero-downtime strategy.
- User says "I think our GitHub token was exposed in a public gist" → EMERGENCY rotation immediately (Security Lead will approve). Act fast.
- User says "SendGrid sent us a security advisory to rotate keys" → Rotate third-party key (CTO will approve since it's third-party).
- User says "We had a full infrastructure breach" → ROTATE ALL KEYS. Nuclear option (CTO + Security Lead must both approve). Explain the blast radius.

For emergencies, act IMMEDIATELY. Explain the rotation strategy (zero-downtime, blue-green) for non-emergency rotations.""",

    "finance": _CORE_BEHAVIOR + """
You are the company's AI Finance Agent. You handle payments, invoices, vendor transfers, and financial operations autonomously.

Your capabilities: Process payments (PayPal/Stripe), send invoices via email, notify finance team via Slack.

Approval rules:
- Under $500: Auto-approved
- $500–$4,999: Manager approval
- $5,000+: CFO approval required
- Daily budget: $10,000 (blocks if exceeded)
- Bulk payments (5+ vendors): CFO + Manager (both must approve)

EXAMPLES:
- "Pay invoice #1234 to Acme Corp for $200 for office supplies" → process_payment($200, "Acme Corp") auto-approved.
- "Transfer $5,000 to the design agency" → process_payment($5,000) → CFO approval needed.
- "Pay all 15 pending vendor invoices, total $50,000" → Try to process bulk payment → BLOCKED (budget exceeded). Adapt by processing individually.
- "Send a receipt to vendor@acme.com" → send_invoice email (auto).

Always state: amount, vendor, which approval tier applies.""",

    "travelops": _CORE_BEHAVIOR + """
You are the company's AI Travel Operations Agent. You book flights, hotels, and ground transportation for employees.

Your capabilities: Book flights, book hotels, arrange ground transportation, send itinerary emails, notify teams via Slack.

Approval rules:
- Economy flights under $500: Auto-approved
- $500–$2,000: Manager approval
- $2,000–$5,000: VP approval
- $5,000+: CFO approval
- Business/first class: Always requires VP approval regardless of amount
- Hotel suites: CFO approval

EXAMPLES:
- "Book economy flight Berlin to London for $200" → book_flight auto-approved.
- "Book business class to San Francisco for 3 people" → $3,000/person × 3 = $9,000 → CFO approval (business class + high amount).
- "Book first class to Tokyo + Ritz-Carlton suite for a week" → Multiple step-ups cascade: first class needs VP, suite needs CFO. Total $15,000+.
- "Arrange airport pickup for the visiting client" → book_transport auto-approved.

For team travel, calculate totals. For luxury bookings, explain why elevated approval is needed.""",

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

For mass communications, always flag the recipient count. External communications represent the company.""",
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
    ],

    "account_takeover": [
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
        {
            "name": "send_notification",
            "description": "Send a security notification email to the affected user.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string"},
                    "subject": {"type": "string"},
                    "type": {"type": "string", "enum": ["account_compromised", "account_restored", "security_alert"]},
                },
                "required": ["recipient", "subject", "type"],
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
            "description": "Send an access change notification to Slack.",
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

    "patient_data": [
        {
            "name": "share_records",
            "description": "Share patient medical records with an authorized recipient.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string", "description": "Patient identifier"},
                    "recipient_type": {"type": "string", "enum": ["own_doctor", "external_clinic", "insurance", "research"]},
                    "recipient_name": {"type": "string"},
                    "purpose": {"type": "string"},
                    "data_scope": {"type": "string", "enum": ["full_record", "summary", "specific_test", "anonymized"]},
                },
                "required": ["patient_id", "recipient_type", "recipient_name", "purpose"],
            },
        },
        {
            "name": "send_notification",
            "description": "Send a data sharing notification email.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string"},
                    "subject": {"type": "string"},
                    "type": {"type": "string", "enum": ["consent_request", "data_shared", "access_granted"]},
                },
                "required": ["recipient", "subject", "type"],
            },
        },
    ],

    "prescription_refill": [
        {
            "name": "process_refill",
            "description": "Process a prescription refill request.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "medication": {"type": "string", "description": "Medication name"},
                    "dosage": {"type": "string", "description": "Dosage (e.g. 10mg, 500mg)"},
                    "is_controlled": {"type": "boolean", "description": "Whether this is a controlled substance"},
                    "is_dosage_change": {"type": "boolean", "description": "Whether this involves a dosage change"},
                    "is_new_prescription": {"type": "boolean", "description": "Whether this is a new prescription"},
                },
                "required": ["patient_id", "medication", "dosage"],
            },
        },
        {
            "name": "notify_pharmacy",
            "description": "Send a notification to the pharmacy.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "pharmacy_name": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["pharmacy_name", "message"],
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

    "api_key_rotation": [
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
            "name": "notify_slack",
            "description": "Send a rotation notification to Slack.",
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

    "finance": [
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
        {
            "name": "send_invoice",
            "description": "Send an invoice or receipt via email.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string", "description": "Recipient email"},
                    "subject": {"type": "string"},
                    "amount_usd": {"type": "number"},
                    "type": {"type": "string", "enum": ["invoice", "receipt", "reminder"]},
                },
                "required": ["recipient", "subject", "type"],
            },
        },
        {
            "name": "notify_slack",
            "description": "Send a finance notification to Slack.",
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

    "travelops": [
        {
            "name": "book_flight",
            "description": "Book a flight for an employee.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "passenger": {"type": "string", "description": "Passenger name"},
                    "origin": {"type": "string", "description": "Departure city/airport"},
                    "destination": {"type": "string", "description": "Arrival city/airport"},
                    "date": {"type": "string", "description": "Travel date (YYYY-MM-DD)"},
                    "cabin_class": {"type": "string", "enum": ["economy", "premium_economy", "business", "first"]},
                    "amount_usd": {"type": "number", "description": "Estimated cost in USD"},
                },
                "required": ["passenger", "origin", "destination", "date", "cabin_class", "amount_usd"],
            },
        },
        {
            "name": "book_hotel",
            "description": "Book a hotel for an employee.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "guest": {"type": "string"},
                    "hotel": {"type": "string", "description": "Hotel name"},
                    "city": {"type": "string"},
                    "check_in": {"type": "string", "description": "Check-in date"},
                    "check_out": {"type": "string", "description": "Check-out date"},
                    "room_type": {"type": "string", "enum": ["standard", "deluxe", "suite"]},
                    "amount_usd": {"type": "number"},
                },
                "required": ["guest", "hotel", "city", "check_in", "check_out", "room_type", "amount_usd"],
            },
        },
        {
            "name": "book_transport",
            "description": "Arrange ground transportation (taxi, car service).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "passenger": {"type": "string"},
                    "pickup": {"type": "string"},
                    "dropoff": {"type": "string"},
                    "date": {"type": "string"},
                    "type": {"type": "string", "enum": ["taxi", "car_service", "shuttle"]},
                    "amount_usd": {"type": "number"},
                },
                "required": ["passenger", "pickup", "dropoff", "date", "type", "amount_usd"],
            },
        },
        {
            "name": "send_itinerary",
            "description": "Send travel itinerary email to the traveler.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string"},
                    "subject": {"type": "string"},
                    "body_preview": {"type": "string"},
                },
                "required": ["recipient", "subject"],
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
    },
    "account_takeover": {
        "freeze_account": {"connection": "salesforce-prod", "action": "update_case",
                           "param_map": lambda p: {"type": "account_freeze", "email": p["account_email"],
                                                   "reason": p["reason"]}},
        "ban_account": {"connection": "salesforce-prod", "action": "update_case",
                        "param_map": lambda p: {"type": "permanent_ban", "email": p["account_email"],
                                                "reason": p["reason"], "evidence": p.get("evidence", "")}},
        "issue_credit": {"connection": "stripe-prod", "action": "credit",
                         "param_map": lambda p: {"amount_usd": p["amount_usd"], "customer": p["account_email"],
                                                 "reason": p["reason"]}},
        "send_notification": {"connection": "gmail-prod", "action": "send_email",
                              "param_map": lambda p: {"recipient": p["recipient"], "subject": p["subject"],
                                                      "type": p["type"]}},
    },
    "recruitment": {
        "send_email": {"connection": "gmail-prod", "action": "send_email",
                       "param_map": lambda p: {k: v for k, v in p.items() if v is not None}},
        "add_to_github": {"connection": "github-prod", "action": "add_member",
                          "param_map": lambda p: p},
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
    "patient_data": {
        "share_records": {"connection": "google-drive-prod", "action": "share",
                          "param_map": lambda p: p},
        "send_notification": {"connection": "gmail-prod", "action": "send_email",
                              "param_map": lambda p: {"recipient": p["recipient"], "subject": p["subject"],
                                                      "type": p["type"]}},
    },
    "prescription_refill": {
        "process_refill": {"connection": "gmail-prod", "action": "send_email",
                           "param_map": lambda p: {"type": "controlled_refill" if p.get("is_controlled") else
                                                   "dosage_change" if p.get("is_dosage_change") else
                                                   "new_prescription" if p.get("is_new_prescription") else
                                                   "routine_refill",
                                                   "patient_id": p["patient_id"],
                                                   "medication": p["medication"], "dosage": p["dosage"],
                                                   "recipient": "pharmacy@clinic.com",
                                                   "subject": f"Rx Refill: {p['medication']} {p['dosage']}"}},
        "notify_pharmacy": {"connection": "slack-prod", "action": "send_message",
                            "param_map": lambda p: {"channel": "#pharmacy",
                                                    "message": p["message"]}},
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
    "api_key_rotation": {
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
        "notify_slack": {"connection": "slack-prod", "action": "send_message",
                         "param_map": lambda p: p},
    },
    "finance": {
        "process_payment": {"connection": "stripe-prod", "action": "charge",
                            "param_map": lambda p: {"amount_usd": p["amount_usd"], "customer": p["vendor"],
                                                    "description": p["description"],
                                                    "invoice_id": p.get("invoice_id", ""),
                                                    "method": p.get("method", "stripe")}},
        "send_invoice": {"connection": "gmail-prod", "action": "send_email",
                         "param_map": lambda p: {"recipient": p["recipient"], "subject": p["subject"],
                                                 "type": p["type"], "amount_usd": p.get("amount_usd", 0)}},
        "notify_slack": {"connection": "slack-prod", "action": "send_message",
                         "param_map": lambda p: p},
    },
    "travelops": {
        "book_flight": {"connection": "stripe-prod", "action": "charge",
                        "param_map": lambda p: {"amount_usd": p["amount_usd"], "customer": p["passenger"],
                                                "description": f"Flight {p['origin']} → {p['destination']} ({p['cabin_class']})",
                                                "type": "travel_flight", "cabin_class": p["cabin_class"]}},
        "book_hotel": {"connection": "stripe-prod", "action": "charge",
                       "param_map": lambda p: {"amount_usd": p["amount_usd"], "customer": p["guest"],
                                               "description": f"Hotel: {p['hotel']} in {p['city']}",
                                               "type": "travel_hotel", "room_type": p["room_type"]}},
        "book_transport": {"connection": "stripe-prod", "action": "charge",
                           "param_map": lambda p: {"amount_usd": p["amount_usd"], "customer": p["passenger"],
                                                   "description": f"Transport: {p['pickup']} → {p['dropoff']}",
                                                   "type": "travel_transport"}},
        "send_itinerary": {"connection": "gmail-prod", "action": "send_email",
                           "param_map": lambda p: {"recipient": p["recipient"], "subject": p["subject"],
                                                   "type": "itinerary"}},
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
        return {
            "connection": tool_def["connection"],
            "action": tool_def["action"],
            "params": params,
        }
    except Exception as e:
        logger.error(f"Tool mapping error: {agent_id}/{tool_name}: {e}")
        return None


# ── Suggestions ───────────────────────────────────────────────────────────────

AGENT_SUGGESTIONS: dict[str, list[str]] = {
    "expense": [
        "I need a second monitor for my home office setup",
        "Our team is planning an offsite dinner for 12 people next Friday",
        "I'm attending KubeCon in Paris next month, need to book flights and hotel",
        "We ran out of whiteboard markers and Post-it notes",
        "My keyboard stopped working, I need a replacement",
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
    ],
    "account_takeover": [
        "Customer alice@gmail.com called saying she sees orders she didn't place",
        "We noticed 50 accounts logged in from the same IP within one minute",
        "The customer from ticket #4821 is asking when their account will be restored",
        "A user reported that their email and password were changed without their knowledge",
        "Our fraud detection flagged three accounts making identical $999 purchases",
    ],
    "recruitment": [
        "We liked the React developer from the portfolio review, let's schedule a call",
        "The backend candidate accepted verbally, salary agreed at $165k, start date March 15",
        "We need to make a competitive offer for the ML engineer — market rate is around $200k",
        "Jake in the QA team has been consistently missing deadlines for 3 months now",
        "New hire Maria starts next Monday, she needs access to our GitHub repos",
    ],
    "access_provisioning": [
        "We have a new junior developer joining the mobile team next week",
        "Lisa got promoted to engineering manager, she'll need broader repo access",
        "Finance team is onboarding a new analyst who needs the reporting tools",
        "Tom from the backend team accepted an offer at another company, last day is Friday",
        "The external contractor's project wrapped up, we should clean up their access",
    ],
    "patient_data": [
        "Dr. Wilson is covering for Dr. Smith today and needs access to his patients",
        "We're referring patient P-2847 to the cardiology department at Mount Sinai",
        "Aetna Insurance sent a records request for patient P-1156, claim #AC-29481",
        "The Johns Hopkins research team needs de-identified data from our cardiac ward",
        "Patient P-3390's family is asking for copies of the recent MRI results",
    ],
    "prescription_refill": [
        "Mrs. Johnson called, she's running low on her Lisinopril 10mg",
        "Patient P-4422 is here for their monthly Adderall 20mg pickup",
        "Dr. Patel reviewed the labs and wants to adjust the Metformin dosage for P-2891",
        "Walk-in patient with strep throat, Dr. Kim wants to prescribe Amoxicillin 500mg",
        "Patient P-1837 is asking about switching from brand to generic for their statin",
    ],
    "gdpr_request": [
        "We received a 'right to be forgotten' email from a user in Berlin",
        "After the acquisition, legal wants to clean up 30 duplicate user accounts",
        "Marketing wants to send EU user analytics to our Mixpanel instance in the US",
        "A former employee is requesting an export of all their personal data we hold",
        "The French DPA sent us a notice about a complaint from one of our users",
    ],
    "api_key_rotation": [
        "Our monitoring shows the Stripe production key is 87 days old",
        "Someone accidentally pushed a .env file to a public repo on GitHub",
        "We got a security bulletin from Twilio recommending all customers rotate keys",
        "After the security audit, the recommendation is to rotate all production credentials",
        "The shared API key with our payment processor expires in 3 days",
    ],
    "finance": [
        "Pay invoice #1234 to Acme Corp for $200 for office supplies",
        "Transfer $5,000 to the design agency for the Q1 branding project, it's overdue",
        "Process all pending vendor payments — 15 vendors, total around $50,000",
        "Send a payment receipt to billing@vendor.com for last month's SaaS subscription",
        "We owe $8,500 to the catering company for the annual conference",
    ],
    "travelops": [
        "Book an economy flight from Berlin to London for next Tuesday, budget around $200",
        "Book business class flights for the team of 3 to the San Francisco conference",
        "Book first class to Tokyo, a Ritz-Carlton suite for a week, and a private car service",
        "We need a hotel near the convention center in Austin for 2 nights, standard room",
        "Arrange airport pickup for the visiting client arriving at JFK Thursday morning",
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

def _execute_tool(agent_id: str, tool_name: str, tool_args: dict, workspace_id: str) -> dict:
    """Execute an ApprovalKit action by querying the DB with a sync session.

    Uses a separate sync SQLAlchemy engine to avoid async event loop conflicts.
    """
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
        sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        engine = create_engine(sync_url)

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

            from api.services.rule_engine import evaluate_conditions
            matched_rule = None
            for rule in rules:
                if evaluate_conditions(rule.conditions or [], action["params"]):
                    matched_rule = rule
                    break

        engine.dispose()

        if not matched_rule:
            # Auto-approved — execute via Token Vault in background
            _fire_token_vault_execution(action["connection"], action["action"], action["params"], workspace_id)
            return {
                "success": True,
                "status": "auto_approved",
                "message": "No matching rule — auto-approved. Action executed via Token Vault.",
                "rule_name": None,
                "connection": action["connection"],
                "action": action["action"],
                "params": action["params"],
            }

        # Create approval job directly in DB (avoid deadlock from self-HTTP call)
        import uuid as _uuid
        from datetime import datetime, timezone, timedelta
        from api.models.approval_job import ApprovalJob, AuditLog

        job_id = _uuid.uuid4()
        job = ApprovalJob(
            id=job_id,
            idempotency_key=f"agent-{_uuid.uuid4()}",
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

        audit = AuditLog(
            job_id=job_id,
            workspace_id=workspace.id,
            event_type="requested",
            binding_message=matched_rule.context_template or f"Approve {action['action']}?",
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

        approvers = []
        try:
            for ra in matched_rule.approvers:
                if hasattr(ra, 'approver') and ra.approver:
                    approvers.append(ra.approver.name)
                elif hasattr(ra, 'name'):
                    approvers.append(ra.name)
        except Exception:
            pass

        return {
            "success": True,
            "status": "pending",
            "message": f"Submitted for approval (Rule: {matched_rule.name}, Model: {matched_rule.model.value}). "
                       f"Approval is async — CONTINUE with your remaining actions immediately.",
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

            engine.dispose()

            if not refresh_token:
                logger.warning(f"Token Vault fire: no token for '{connection}'")
                return

            # Try Token Exchange first, fall back to stored token
            access_token = None
            provider = auth0_conn_name or service
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
                logger.info(f"Token Exchange response: {token_resp.status_code}")
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
                # Slack API: chat.postMessage
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

_PROVIDER_CONFIG = {
    "ollama": {"type": "openai", "base_url": "http://ollama:11434/v1", "model": "qwen2.5:7b", "needs_api_key": False},
    "gemini": {"type": "gemini", "model": "models/gemini-2.0-flash"},
    "groq": {"type": "openai", "base_url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile"},
    "openrouter": {"type": "openai", "base_url": "https://openrouter.ai/api/v1", "model": "meta-llama/llama-3.3-70b-instruct:free"},
    "mistral": {"type": "openai", "base_url": "https://api.mistral.ai/v1", "model": "mistral-small-latest"},
}


def process_message(agent_id: str, message: str, agent_title: str = "", session_id: str = "", api_key: str = "", provider: str = "gemini", workspace_id: str = "") -> dict:
    """Agentic loop: LLM thinks → calls tool → backend executes → result fed back → LLM responds.

    Supports multiple providers: Gemini, Groq, OpenRouter, Mistral.
    The LLM never just "suggests" an action — it executes it server-side and
    responds with full knowledge of the outcome.

    Max 5 tool calls per turn to prevent infinite loops.
    """
    MAX_TOOL_ROUNDS = 5

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

    system_prompt = AGENT_PROMPTS.get(agent_id, f"You are a helpful AI assistant called {agent_title}.")
    tools = AGENT_TOOLS.get(agent_id, [])

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
            temperature=0.7,
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
    MAX_TOOL_ROUNDS = 5

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

            # Tool call present — only collect text if it's NOT json garbage
            if msg.content and not msg.content.strip().startswith("{"):
                all_text_parts.append(msg.content)

            # Add assistant message with tool calls to conversation
            msg_dict = {"role": msg.role, "content": msg.content or ""}
            msg_dict["tool_calls"] = [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]
            messages.append(msg_dict)

            # Execute ONLY the first tool call (one at a time for reliability)
            import json as _json
            tc = msg.tool_calls[0]
            tool_args = _json.loads(tc.function.arguments) if tc.function.arguments else {}

            logger.info(f"Agent {agent_id} calling tool: {tc.function.name}({tool_args})")

            result = _execute_tool(agent_id, tc.function.name, tool_args, workspace_id)
            all_actions.append({"tool": tc.function.name, "args": tool_args, "result": result})

            logger.info(f"Tool result: {result.get('status', 'error')} — {result.get('message', result.get('error', ''))}")

            # Add tool result to messages so LLM sees it and decides next action
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": _json.dumps(result),
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

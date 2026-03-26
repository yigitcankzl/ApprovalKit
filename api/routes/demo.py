"""
Demo Seed Endpoint
==================
POST /api/v1/demo/seed

Idempotently creates all connections, approvers, and rules needed
for the Agent Demos page. Safe to call multiple times — skips
resources that already exist.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.approver import Approver
from api.models.connection import ServiceConnection
from api.models.rule import Rule, RuleApprover, ApprovalModel, TimeoutAction
from api.models.workspace import Workspace
from api.middleware.workspace import get_current_workspace

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

# ── Seed data definitions ─────────────────────────────────────────────────────

CONNECTIONS = [
    {"name": "Stripe Production",  "service": "stripe", "slug": "stripe-prod",
     "actions": ["charge", "refund", "payout", "wire_transfer", "vendor_payment"]},
    {"name": "Slack Production",   "service": "slack",  "slug": "slack-prod",
     "actions": ["send_message"]},
    {"name": "Gmail Production",   "service": "gmail",  "slug": "gmail-prod",
     "actions": ["send_email", "press_release"]},
    {"name": "GitHub Production",  "service": "github", "slug": "github-prod",
     "actions": ["add_member", "remove_member", "deploy", "rollback", "merge_pr"]},
    {"name": "GitHub Main",        "service": "github", "slug": "github-main",
     "actions": ["deploy", "rollback", "merge_pr"]},
    {"name": "AWS Lab",            "service": "aws",    "slug": "aws-lab",
     "actions": ["provision_compute"]},
    {"name": "arXiv",              "service": "arxiv",  "slug": "arxiv",
     "actions": ["submit_paper"]},
]

APPROVERS = [
    {"name": "Sales Manager",  "email": "sales_manager@demo.approvalkit.io",
     "auth0_user_id": "demo|sales_manager",  "role": "sales_manager"},
    {"name": "CFO",            "email": "cfo@demo.approvalkit.io",
     "auth0_user_id": "demo|cfo",            "role": "cfo"},
    {"name": "CS Agent",       "email": "cs_agent@demo.approvalkit.io",
     "auth0_user_id": "demo|cs_agent",       "role": "cs_agent"},
    {"name": "CS Manager",     "email": "cs_manager@demo.approvalkit.io",
     "auth0_user_id": "demo|cs_manager",     "role": "cs_manager"},
    {"name": "Team Lead",      "email": "team_lead@demo.approvalkit.io",
     "auth0_user_id": "demo|team_lead",      "role": "team_lead"},
    {"name": "HR Manager",     "email": "hr_manager@demo.approvalkit.io",
     "auth0_user_id": "demo|hr_manager",     "role": "hr_manager"},
    {"name": "CEO",            "email": "ceo@demo.approvalkit.io",
     "auth0_user_id": "demo|ceo",            "role": "ceo"},
    {"name": "IT Manager",     "email": "it_manager@demo.approvalkit.io",
     "auth0_user_id": "demo|it_manager",     "role": "it_manager"},
    {"name": "CTO",            "email": "cto@demo.approvalkit.io",
     "auth0_user_id": "demo|cto",            "role": "cto"},
    {"name": "Maintainer",     "email": "maintainer@demo.approvalkit.io",
     "auth0_user_id": "demo|maintainer",     "role": "maintainer"},
    {"name": "Lead Engineer",  "email": "lead_eng@demo.approvalkit.io",
     "auth0_user_id": "demo|lead_engineer",  "role": "lead_engineer"},
    {"name": "Treasurer",      "email": "treasurer@demo.approvalkit.io",
     "auth0_user_id": "demo|treasurer",      "role": "treasurer"},
    {"name": "Lead Maintainer","email": "lead_maint@demo.approvalkit.io",
     "auth0_user_id": "demo|lead_maintainer","role": "lead_maintainer"},
    {"name": "PI",             "email": "pi@demo.approvalkit.io",
     "auth0_user_id": "demo|pi",             "role": "pi"},
    {"name": "Finance Dept",   "email": "finance@demo.approvalkit.io",
     "auth0_user_id": "demo|finance",        "role": "finance"},
    {"name": "Operations",     "email": "operations@demo.approvalkit.io",
     "auth0_user_id": "demo|operations",     "role": "operations"},
    {"name": "Procurement",    "email": "procurement@demo.approvalkit.io",
     "auth0_user_id": "demo|procurement",    "role": "procurement"},
    {"name": "Legal",          "email": "legal@demo.approvalkit.io",
     "auth0_user_id": "demo|legal",          "role": "legal"},
    {"name": "Marketing Lead", "email": "marketing@demo.approvalkit.io",
     "auth0_user_id": "demo|marketing",      "role": "marketing"},
    {"name": "PR Manager",     "email": "pr@demo.approvalkit.io",
     "auth0_user_id": "demo|pr",             "role": "pr"},
    {"name": "Manager",        "email": "manager@demo.approvalkit.io",
     "auth0_user_id": "demo|manager",        "role": "manager"},
]


def _build_rules(ar: dict[str, uuid.UUID]) -> list[dict]:
    """
    Returns a list of rule definition dicts.
    `ar` maps role name → approver UUID.
    Conditions use the structured format: {field, operator, value}.
    """
    def c(field: str, op: str, value: Any) -> dict:
        return {"field": field, "operator": op, "value": value}

    return [
        # ── E-Commerce: Stripe charge ─────────────────────────────────────────
        {
            "name": "[Demo] Stripe charge — medium ($100–$999)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Charge ${amount_usd} for {customer} — {description}",
            "conditions": [c("amount_usd", "gte", 100), c("amount_usd", "lt", 1000)],
            "approver_roles": ["sales_manager"],
            "priority": 20,
        },
        {
            "name": "[Demo] Stripe charge — large ($1000+)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "LARGE charge ${amount_usd} for {customer} — {description}",
            "conditions": [c("amount_usd", "gte", 1000)],
            "approver_roles": ["sales_manager", "cfo"],
            "priority": 30,
        },

        # ── E-Commerce: Stripe refund ─────────────────────────────────────────
        {
            "name": "[Demo] Stripe refund — small (<$50)",
            "connection": "stripe-prod", "action": "refund",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Refund ${amount_usd} for {customer} — {reason}",
            "conditions": [c("amount_usd", "lt", 50)],
            "approver_roles": ["cs_agent"],
            "priority": 10,
        },
        {
            "name": "[Demo] Stripe refund — large ($50+)",
            "connection": "stripe-prod", "action": "refund",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 300,
            "context_template": "Refund ${amount_usd} for {customer} — {reason}",
            "conditions": [c("amount_usd", "gte", 50)],
            "approver_roles": ["cs_manager"],
            "partial_approval": True,
            "priority": 20,
        },

        # ── E-Commerce: Slack ─────────────────────────────────────────────────
        {
            "name": "[Demo] Slack #general",
            "connection": "slack-prod", "action": "send_message",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Post to {channel}: {message}",
            "conditions": [c("channel", "eq", "#general")],
            "approver_roles": ["team_lead"],
            "priority": 10,
        },
        {
            "name": "[Demo] Slack #finance",
            "connection": "slack-prod", "action": "send_message",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 300,
            "context_template": "Post to {channel}: {message}",
            "conditions": [c("channel", "eq", "#finance")],
            "approver_roles": ["cfo"],
            "priority": 20,
        },
        {
            "name": "[Demo] Slack #hr",
            "connection": "slack-prod", "action": "send_message",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 300,
            "context_template": "HR post to {channel}: {message}",
            "conditions": [c("channel", "eq", "#hr")],
            "approver_roles": ["hr_manager"],
            "priority": 15,
        },

        # ── HR: Gmail ─────────────────────────────────────────────────────────
        {
            "name": "[Demo] Gmail offer letter",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Send {type} to {recipient}: {subject}",
            "conditions": [c("type", "eq", "offer_letter")],
            "approver_roles": ["hr_manager"],
            "priority": 20,
        },
        {
            "name": "[Demo] Gmail termination letter",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "TERMINATION email to {recipient}: {subject}",
            "conditions": [c("type", "eq", "termination")],
            "approver_roles": ["hr_manager", "ceo"],
            "priority": 30,
        },
        {
            "name": "[Demo] Gmail mass email (500+)",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 600,
            "context_template": "Mass email to {recipient_count} recipients: {subject}",
            "conditions": [c("recipient_count", "gte", 500)],
            "approver_roles": ["marketing"],
            "priority": 25,
        },
        {
            "name": "[Demo] Gmail mass email legal review (10k+)",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "MASS email to {recipient_count} recipients: {subject}",
            "conditions": [c("recipient_count", "gte", 10000)],
            "approver_roles": ["marketing", "legal"],
            "priority": 35,
        },
        {
            "name": "[Demo] Gmail press release",
            "connection": "gmail-prod", "action": "press_release",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "Press release: {headline}",
            "conditions": [],
            "approver_roles": ["pr", "legal", "ceo"],
            "priority": 40,
        },

        # ── HR: GitHub ────────────────────────────────────────────────────────
        {
            "name": "[Demo] GitHub add member (role=member)",
            "connection": "github-prod", "action": "add_member",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 300,
            "context_template": "Add {username} to {org} as {role}",
            "conditions": [c("role", "eq", "member")],
            "approver_roles": ["it_manager"],
            "priority": 10,
        },
        {
            "name": "[Demo] GitHub add member (role=admin)",
            "connection": "github-prod", "action": "add_member",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "Add {username} to {org} as ADMIN",
            "conditions": [c("role", "eq", "admin")],
            "approver_roles": ["it_manager", "cto"],
            "priority": 20,
        },
        {
            "name": "[Demo] GitHub remove member",
            "connection": "github-prod", "action": "remove_member",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "Remove {username} from {org} — {reason}",
            "conditions": [],
            "approver_roles": ["it_manager", "hr_manager"],
            "priority": 20,
        },

        # ── DevOps ────────────────────────────────────────────────────────────
        {
            "name": "[Demo] GitHub deploy — production",
            "connection": "github-main", "action": "deploy",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Deploy {ref} to {environment}",
            "conditions": [c("environment", "eq", "production")],
            "approver_roles": ["maintainer"],
            "priority": 20,
        },
        {
            "name": "[Demo] GitHub rollback — production",
            "connection": "github-main", "action": "rollback",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 300,
            "context_template": "Rollback {env} to {version} — {reason}",
            "conditions": [c("env", "eq", "production")],
            "approver_roles": ["lead_engineer"],
            "priority": 30,
        },

        # ── Open Source ───────────────────────────────────────────────────────
        {
            "name": "[Demo] PR merge — large (200+ lines)",
            "connection": "github-main", "action": "merge_pr",
            "model": ApprovalModel.K_OF_N, "timeout_seconds": 600,
            "k_value": 2,
            "context_template": "Merge PR #{pr_number}: {title} ({lines_changed} lines)",
            "conditions": [c("lines_changed", "gte", 200)],
            "approver_roles": ["maintainer", "lead_maintainer", "cto"],
            "priority": 20,
        },
        {
            "name": "[Demo] Treasury payout — large ($100+)",
            "connection": "stripe-prod", "action": "payout",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "Treasury payout ${amount_usd} to {recipient} — {purpose}",
            "conditions": [c("amount_usd", "gte", 100)],
            "approver_roles": ["treasurer", "lead_maintainer"],
            "priority": 20,
        },

        # ── Research Lab ──────────────────────────────────────────────────────
        {
            "name": "[Demo] AWS compute — medium ($50–$499)",
            "connection": "aws-lab", "action": "provision_compute",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Provision {instance_type} for {hours}h (${estimated_cost_usd})",
            "conditions": [c("estimated_cost_usd", "gte", 50), c("estimated_cost_usd", "lt", 500)],
            "approver_roles": ["pi"],
            "priority": 20,
        },
        {
            "name": "[Demo] AWS compute — large ($500+)",
            "connection": "aws-lab", "action": "provision_compute",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "LARGE compute job {instance_type} × {hours}h (${estimated_cost_usd})",
            "conditions": [c("estimated_cost_usd", "gte", 500)],
            "approver_roles": ["pi", "finance"],
            "priority": 30,
        },
        {
            "name": "[Demo] Paper submission",
            "connection": "arxiv", "action": "submit_paper",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "Submit '{title}' to {target_journal}",
            "conditions": [],
            "approver_roles": ["pi", "hr_manager", "cto"],
            "priority": 10,
        },

        # ── Fintech ───────────────────────────────────────────────────────────
        {
            "name": "[Demo] Payout — standard ($1k–$50k)",
            "connection": "stripe-prod", "action": "payout",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Payout ${amount_usd} to {recipient} ({reference})",
            "conditions": [c("amount_usd", "gte", 1000), c("amount_usd", "lt", 50000)],
            "approver_roles": ["manager"],
            "priority": 10,
        },
        {
            "name": "[Demo] Wire transfer ($50k+) — sequential",
            "connection": "stripe-prod", "action": "wire_transfer",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "Wire ${amount_usd} to {beneficiary}",
            "conditions": [c("amount_usd", "gte", 50000)],
            "approver_roles": ["operations", "finance", "cfo"],
            "priority": 40,
        },
        {
            "name": "[Demo] New vendor payment",
            "connection": "stripe-prod", "action": "vendor_payment",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "New vendor payment ${amount_usd} to {vendor_name}",
            "conditions": [c("is_new_vendor", "eq", True)],
            "approver_roles": ["procurement", "legal"],
            "priority": 30,
        },
    ]


# ── Seed endpoint ──────────────────────────────────────────────────────────────

# Agent → rule name prefix mapping
AGENT_RULES = {
    "ecommerce": ["Stripe charge", "Stripe refund", "Slack"],
    "hr": ["Gmail offer", "Gmail termination", "Gmail mass email", "Gmail press", "GitHub add member", "GitHub remove member"],
    "devops": ["GitHub deploy", "GitHub rollback"],
    "opensource": ["PR merge", "Treasury payout"],
    "research": ["AWS compute", "Paper submission"],
    "fintech": ["Payout", "Wire transfer", "New vendor"],
}

# Agent → required connections
AGENT_CONNECTIONS = {
    "ecommerce": ["stripe-prod", "slack-prod"],
    "hr": ["gmail-prod", "github-prod"],
    "devops": ["github-main"],
    "opensource": ["github-main", "stripe-prod"],
    "research": ["aws-lab", "arxiv"],
    "fintech": ["stripe-prod"],
}

# Agent → required approver roles
AGENT_APPROVERS = {
    "ecommerce": ["sales_manager", "cfo", "cs_agent", "cs_manager", "team_lead"],
    "hr": ["hr_manager", "ceo", "it_manager"],
    "devops": ["maintainer", "lead_engineer", "cto"],
    "opensource": ["maintainer", "lead_maintainer", "cto", "treasurer"],
    "research": ["pi", "finance", "hr_manager", "cto"],
    "fintech": ["manager", "operations", "finance", "cfo", "procurement", "legal"],
}


# ── Demo agent catalog ────────────────────────────────────────────────────────

DEMO_AGENTS = [
    {
        "id": "ecommerce",
        "title": "E-Commerce Agent",
        "icon": "ShoppingCart",
        "description": "AI shopping agent that processes Stripe payments and refunds. Amount tiers trigger different approval chains — small orders pass automatically, large ones require step-up approval.",
        "setupInfo": [
            {"type": "connection", "name": "stripe-prod", "detail": "Stripe payments (charge, refund)"},
            {"type": "connection", "name": "slack-prod", "detail": "Team notifications (#general, #finance, #hr)"},
            {"type": "approver", "name": "Sales Manager", "detail": "Approves medium charges ($100-$999)"},
            {"type": "approver", "name": "CFO", "detail": "Co-approves large charges ($1000+)"},
            {"type": "approver", "name": "CS Agent", "detail": "Approves small refunds (<$50)"},
            {"type": "approver", "name": "CS Manager", "detail": "Approves large refunds ($50+), can edit amount"},
            {"type": "approver", "name": "Team Lead", "detail": "Approves Slack posts to #general"},
            {"type": "rule", "name": "Stripe charge — medium ($100-999)", "detail": "any_one → Sales Manager"},
            {"type": "rule", "name": "Stripe charge — large ($1000+)", "detail": "all_of_n → Sales Manager + CFO"},
            {"type": "rule", "name": "Stripe refund — small (<$50)", "detail": "any_one → CS Agent"},
            {"type": "rule", "name": "Stripe refund — large ($50+)", "detail": "specific → CS Manager (partial approval)"},
            {"type": "rule", "name": "Slack #general", "detail": "any_one → Team Lead"},
            {"type": "rule", "name": "Slack #finance", "detail": "specific → CFO"},
        ],
        "scenarios": [
            {
                "title": "Small charge ($49)",
                "description": "Under threshold — no rule matches, auto-approved instantly.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"amount_usd": 49, "customer": "alice@example.com", "description": "T-shirt"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "E-Commerce Agent", "sub": "charge_customer(49, ...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Stripe Charge", "sub": "$49 → alice@example.com"},
                ],
            },
            {
                "title": "Medium charge ($349)",
                "description": "Sales manager receives a Guardian push and taps Approve.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"amount_usd": 349, "customer": "bob@example.com", "description": "Premium plan"},
                "badge": "info", "badgeLabel": "any_one",
                "flow": [
                    {"type": "agent", "label": "E-Commerce Agent", "sub": "charge_customer(349, ...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: medium charge"},
                    {"type": "approver", "label": "Sales Manager", "sub": "Guardian push → Approve"},
                    {"type": "action", "label": "Stripe Charge", "sub": "$349 → bob@example.com"},
                ],
            },
            {
                "title": "Large charge ($5,000) — STEP-UP",
                "description": "Both sales_manager and CFO must approve. all_of_n — neither can skip the other.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"amount_usd": 5000, "customer": "corp@example.com", "description": "Enterprise license"},
                "badge": "warning", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "E-Commerce Agent", "sub": "charge_customer(5000, ...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: large charge (step-up)"},
                    {"type": "approver", "label": "Sales Manager", "sub": "Guardian push → Approve"},
                    {"type": "approver", "label": "CFO", "sub": "Guardian push → Approve"},
                    {"type": "action", "label": "Stripe Charge", "sub": "$5,000 → corp@example.com"},
                ],
            },
            {
                "title": "Refund ($340) — partial approval",
                "description": "CS Manager may reduce the refund amount before approving.",
                "connection": "stripe-prod", "action": "refund",
                "params": {"amount_usd": 340, "customer": "alice@example.com", "reason": "Wrong size"},
                "badge": "default", "badgeLabel": "partial",
                "flow": [
                    {"type": "agent", "label": "E-Commerce Agent", "sub": "refund_customer(340, ...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: large refund"},
                    {"type": "approver", "label": "CS Manager", "sub": "May edit params → Approve"},
                    {"type": "action", "label": "Stripe Refund", "sub": "$340 (or modified) → alice"},
                ],
            },
        ],
    },
    {
        "id": "hr",
        "title": "HR Agent",
        "icon": "Users",
        "description": "AI HR assistant handling hiring, offboarding, and team communication. Termination emails require both HR Manager and CEO. GitHub access removal requires IT + HR sign-off.",
        "setupInfo": [
            {"type": "connection", "name": "gmail-prod", "detail": "Email (offer letters, terminations)"},
            {"type": "connection", "name": "github-prod", "detail": "GitHub org member management"},
            {"type": "approver", "name": "HR Manager", "detail": "Approves offer letters, co-approves terminations"},
            {"type": "approver", "name": "CEO", "detail": "Co-approves termination emails"},
            {"type": "approver", "name": "IT Manager", "detail": "Co-approves GitHub access removal"},
            {"type": "rule", "name": "Gmail offer letter", "detail": "specific → HR Manager"},
            {"type": "rule", "name": "Gmail termination", "detail": "all_of_n → HR Manager + CEO"},
            {"type": "rule", "name": "GitHub remove member", "detail": "all_of_n → IT Manager + HR Manager"},
            {"type": "rule", "name": "GitHub add member (admin)", "detail": "specific → CTO"},
        ],
        "scenarios": [
            {
                "title": "Interview invite",
                "description": "Low-risk email — auto-approved, no rule needed.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "invite", "recipient": "candidate@example.com", "subject": "Interview invitation"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "HR Agent", "sub": "send_email(type=invite, ...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Gmail Send", "sub": "Invite → candidate"},
                ],
            },
            {
                "title": "Offer letter",
                "description": "HR Manager must review salary and terms before sending.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "offer_letter", "recipient": "hire@example.com", "subject": "Offer: $180k Senior Eng"},
                "badge": "info", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "HR Agent", "sub": "send_email(type=offer_letter, ...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: offer letter"},
                    {"type": "approver", "label": "HR Manager", "sub": "Guardian push → Approve"},
                    {"type": "action", "label": "Gmail Send", "sub": "Offer letter → hire@example.com"},
                ],
            },
            {
                "title": "Termination letter — all_of_n",
                "description": "Highest sensitivity. HR Manager and CEO must both approve before sending.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "termination", "recipient": "employee@example.com", "subject": "Employment Termination"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "HR Agent", "sub": "send_email(type=termination, ...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: termination"},
                    {"type": "approver", "label": "HR Manager", "sub": "Guardian push → Approve"},
                    {"type": "approver", "label": "CEO", "sub": "Guardian push → Approve"},
                    {"type": "action", "label": "Gmail Send", "sub": "Termination → employee"},
                ],
            },
            {
                "title": "GitHub remove member — IT + HR",
                "description": "Offboarding: both IT Manager and HR Manager confirm before revoking access.",
                "connection": "github-prod", "action": "remove_member",
                "params": {"username": "employee", "org": "acme-corp", "reason": "Employment terminated"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "HR Agent", "sub": "remove_github_member(...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: remove member"},
                    {"type": "approver", "label": "IT Manager", "sub": "Guardian push → Approve"},
                    {"type": "approver", "label": "HR Manager", "sub": "Guardian push → Approve"},
                    {"type": "action", "label": "GitHub API", "sub": "Remove employee from acme-corp"},
                ],
            },
        ],
    },
    {
        "id": "devops",
        "title": "DevOps Agent",
        "icon": "Server",
        "description": "CI/CD agent managing GitHub deployments. Staging is always auto-approved. Production needs a maintainer. Rollbacks require the lead engineer only.",
        "setupInfo": [
            {"type": "connection", "name": "github-main", "detail": "GitHub deployments and rollbacks"},
            {"type": "approver", "name": "Maintainer", "detail": "Approves production deployments"},
            {"type": "approver", "name": "Lead Engineer", "detail": "Approves rollbacks (specific)"},
            {"type": "approver", "name": "CTO", "detail": "Backup escalation"},
            {"type": "rule", "name": "GitHub deploy — production", "detail": "any_one → Maintainer"},
            {"type": "rule", "name": "GitHub rollback — production", "detail": "specific → Lead Engineer"},
        ],
        "scenarios": [
            {
                "title": "Deploy to staging",
                "description": "Staging deployments are always safe — no approval gate.",
                "connection": "github-main", "action": "deploy",
                "params": {"ref": "main", "environment": "staging", "service": "api"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "DevOps Agent", "sub": "deploy(env=staging)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "GitHub Actions", "sub": "Deploy main → staging"},
                ],
            },
            {
                "title": "Deploy to production",
                "description": "Any maintainer can approve. First response unblocks the deploy.",
                "connection": "github-main", "action": "deploy",
                "params": {"ref": "v2.4.1", "environment": "production", "service": "api"},
                "badge": "info", "badgeLabel": "any_one",
                "flow": [
                    {"type": "agent", "label": "DevOps Agent", "sub": "deploy(env=production, ref=v2.4.1)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: production deploy"},
                    {"type": "approver", "label": "Maintainer", "sub": "Guardian push → Approve"},
                    {"type": "action", "label": "GitHub Actions", "sub": "Deploy v2.4.1 → production"},
                ],
            },
            {
                "title": "Production rollback",
                "description": "Only the lead engineer can approve a rollback — specific model.",
                "connection": "github-main", "action": "rollback",
                "params": {"env": "production", "version": "v2.3.8", "reason": "p0 latency spike"},
                "badge": "warning", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "DevOps Agent", "sub": "rollback(env=production, v2.3.8)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: rollback (specific)"},
                    {"type": "approver", "label": "Lead Engineer", "sub": "Guardian push → Approve"},
                    {"type": "action", "label": "GitHub Actions", "sub": "Rollback production → v2.3.8"},
                ],
            },
        ],
    },
    {
        "id": "opensource",
        "title": "Open Source Bot",
        "icon": "Package",
        "description": "Governance bot for an open source project. Large PRs require a k-of-n maintainer vote. Treasury disbursements above $100 need the lead plus the treasurer.",
        "setupInfo": [
            {"type": "connection", "name": "github-main", "detail": "PR merges"},
            {"type": "connection", "name": "stripe-prod", "detail": "Treasury payouts"},
            {"type": "approver", "name": "Maintainer", "detail": "PR review vote"},
            {"type": "approver", "name": "Lead Maintainer", "detail": "PR review + treasury co-sign"},
            {"type": "approver", "name": "CTO", "detail": "PR review vote"},
            {"type": "approver", "name": "Treasurer", "detail": "Treasury co-sign"},
            {"type": "rule", "name": "PR merge — large (200+ lines)", "detail": "k_of_n (2/3) → Maintainer, Lead, CTO"},
            {"type": "rule", "name": "Treasury payout — large ($100+)", "detail": "all_of_n → Treasurer + Lead Maintainer"},
        ],
        "scenarios": [
            {
                "title": "Small PR (42 lines) — auto-merge",
                "description": "Tiny diffs auto-merge without bothering maintainers.",
                "connection": "github-main", "action": "merge_pr",
                "params": {"pr_number": 1847, "title": "fix: typo in README", "lines_changed": 42, "author": "contributor"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "OSS Bot", "sub": "merge_pr(#1847, 42 lines)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "GitHub", "sub": "Merge PR #1847"},
                ],
            },
            {
                "title": "Large PR (380 lines) — k-of-n vote",
                "description": "At least 2 out of 3 maintainers must approve within the quorum window.",
                "connection": "github-main", "action": "merge_pr",
                "params": {"pr_number": 1901, "title": "feat: rewrite core parser", "lines_changed": 380, "author": "core-dev"},
                "badge": "warning", "badgeLabel": "k_of_n",
                "flow": [
                    {"type": "agent", "label": "OSS Bot", "sub": "merge_pr(#1901, 380 lines)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: large PR (k=2/3)"},
                    {"type": "approver", "label": "Maintainer A", "sub": "Guardian push"},
                    {"type": "approver", "label": "Maintainer B", "sub": "Guardian push"},
                    {"type": "gate", "label": "Quorum met (2/3)", "sub": "Within window"},
                    {"type": "action", "label": "GitHub", "sub": "Merge PR #1901"},
                ],
            },
            {
                "title": "Treasury payout $500 — all_of_n",
                "description": "Both treasurer and lead maintainer must sign off on large disbursements.",
                "connection": "stripe-prod", "action": "payout",
                "params": {"amount_usd": 500, "recipient": "infra@example.com", "purpose": "Annual hosting"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "OSS Bot", "sub": "treasury_payout(500, ...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: large treasury spend"},
                    {"type": "approver", "label": "Treasurer", "sub": "Guardian push → Approve"},
                    {"type": "approver", "label": "Lead Maintainer", "sub": "Guardian push → Approve"},
                    {"type": "action", "label": "Stripe Payout", "sub": "$500 → infra@example.com"},
                ],
            },
        ],
    },
    {
        "id": "research",
        "title": "Research Lab Agent",
        "icon": "FlaskConical",
        "description": "Lab assistant that provisions compute, submits papers, and manages grant budgets. Paper submissions require every co-author to approve. Large AWS jobs need the PI plus finance.",
        "setupInfo": [
            {"type": "connection", "name": "aws-lab", "detail": "AWS compute provisioning"},
            {"type": "connection", "name": "arxiv", "detail": "Paper submissions"},
            {"type": "approver", "name": "PI", "detail": "Approves compute and papers"},
            {"type": "approver", "name": "Finance Dept", "detail": "Co-approves large compute ($500+)"},
            {"type": "rule", "name": "AWS compute — medium ($50-499)", "detail": "any_one → PI"},
            {"type": "rule", "name": "AWS compute — large ($500+)", "detail": "all_of_n → PI + Finance"},
            {"type": "rule", "name": "Paper submission", "detail": "all_of_n → PI + HR + CTO"},
        ],
        "scenarios": [
            {
                "title": "Small compute job ($12) — auto",
                "description": "Cheap jobs spin up immediately without interrupting researchers.",
                "connection": "aws-lab", "action": "provision_compute",
                "params": {"instance_type": "t3.medium", "hours": 4, "project": "nlp-exp-42", "estimated_cost_usd": 12},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Lab Agent", "sub": "provision_compute($12)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "AWS", "sub": "Spin up t3.medium × 4h"},
                ],
            },
            {
                "title": "Paper submission — all co-authors",
                "description": "All 3 co-authors are notified in parallel and must each approve before submission.",
                "connection": "arxiv", "action": "submit_paper",
                "params": {"title": "Efficient Human-in-the-Loop Approval for AI", "authors": ["Dr. Smith", "Dr. Jones", "Dr. Lee"], "target_journal": "NeurIPS 2026"},
                "badge": "warning", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Lab Agent", "sub": "submit_paper(...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: paper submission"},
                    {"type": "approver", "label": "Dr. Smith", "sub": "Guardian push → Approve"},
                    {"type": "approver", "label": "Dr. Jones", "sub": "Guardian push → Approve"},
                    {"type": "approver", "label": "Dr. Lee", "sub": "Guardian push → Approve"},
                    {"type": "action", "label": "arXiv API", "sub": "Submit to NeurIPS 2026"},
                ],
            },
            {
                "title": "Grant spend $1,200 — PI + Finance",
                "description": "Both the Principal Investigator and Finance department must approve grant expenditures.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"amount_usd": 1200, "project": "NIH-2025-003", "purpose": "Conference travel"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Lab Agent", "sub": "grant_spend(1200, ...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: grant spend"},
                    {"type": "approver", "label": "PI", "sub": "Guardian push → Approve"},
                    {"type": "approver", "label": "Finance Dept", "sub": "Guardian push → Approve"},
                    {"type": "action", "label": "Stripe Charge", "sub": "$1,200 from grant account"},
                ],
            },
        ],
    },
    {
        "id": "fintech",
        "title": "Financial Services",
        "icon": "CreditCard",
        "description": "Payment agent with a strict compliance chain. Wire transfers always go through a three-step sequential approval: Operations → Finance → CFO. New vendors need procurement and legal.",
        "setupInfo": [
            {"type": "connection", "name": "stripe-prod", "detail": "Payouts, wire transfers, vendor payments"},
            {"type": "approver", "name": "Manager", "detail": "Approves standard payouts ($1k-$50k)"},
            {"type": "approver", "name": "Operations", "detail": "Wire transfer step 1"},
            {"type": "approver", "name": "Finance Dept", "detail": "Wire transfer step 2 + vendor co-sign"},
            {"type": "approver", "name": "CFO", "detail": "Wire transfer step 3"},
            {"type": "approver", "name": "Procurement", "detail": "New vendor vetting"},
            {"type": "approver", "name": "Legal", "detail": "New vendor legal clearance"},
            {"type": "rule", "name": "Payout — standard ($1k-$50k)", "detail": "any_one → Manager"},
            {"type": "rule", "name": "Wire transfer ($50k+)", "detail": "all_of_n → Ops + Finance + CFO"},
            {"type": "rule", "name": "New vendor payment", "detail": "all_of_n → Procurement + Legal"},
        ],
        "scenarios": [
            {
                "title": "Standard payout $4,500",
                "description": "Manager approves routine supplier payments.",
                "connection": "stripe-prod", "action": "payout",
                "params": {"amount_usd": 4500, "recipient": "supplier@example.com", "reference": "INV-2026-0441"},
                "badge": "info", "badgeLabel": "any_one",
                "flow": [
                    {"type": "agent", "label": "Fintech Agent", "sub": "send_payout(4500, ...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: standard payout"},
                    {"type": "approver", "label": "Manager", "sub": "Guardian push → Approve"},
                    {"type": "action", "label": "Stripe Payout", "sub": "$4,500 → supplier"},
                ],
            },
            {
                "title": "Wire transfer $250,000 — sequential chain",
                "description": "Ops approves first, then Finance, then CFO. Each step only starts after the previous approval.",
                "connection": "stripe-prod", "action": "wire_transfer",
                "params": {"amount_usd": 250000, "beneficiary": "Acme Holdings", "purpose": "Series B tranche"},
                "badge": "danger", "badgeLabel": "sequential",
                "flow": [
                    {"type": "agent", "label": "Fintech Agent", "sub": "wire_transfer(250k, ...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: wire transfer"},
                    {"type": "approver", "label": "Operations", "sub": "Step 1 → Approve"},
                    {"type": "approver", "label": "Finance", "sub": "Step 2 → Approve"},
                    {"type": "approver", "label": "CFO", "sub": "Step 3 → Approve"},
                    {"type": "action", "label": "Stripe Wire", "sub": "$250,000 → Acme Holdings"},
                ],
            },
            {
                "title": "New vendor payment — procurement + legal",
                "description": "New vendors must be vetted by procurement and cleared by legal before any payment.",
                "connection": "stripe-prod", "action": "vendor_payment",
                "params": {"vendor_name": "NewCloud GmbH", "amount_usd": 12000, "is_new_vendor": True, "invoice_id": "INV-NC-001"},
                "badge": "warning", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Fintech Agent", "sub": "pay_vendor(is_new_vendor=True)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: new vendor"},
                    {"type": "approver", "label": "Procurement", "sub": "Guardian push → Approve"},
                    {"type": "approver", "label": "Legal", "sub": "Guardian push → Approve"},
                    {"type": "action", "label": "Stripe Payment", "sub": "$12,000 → NewCloud GmbH"},
                ],
            },
        ],
    },
    {
        "id": "comms",
        "title": "Communications Agent",
        "icon": "Mail",
        "description": "Marketing and PR agent that sends emails and press releases. Audience size drives the approval level — small batches are automatic, mass sends need legal review, press releases need the CEO.",
        "setupInfo": [
            {"type": "connection", "name": "gmail-prod", "detail": "Email sending and press releases"},
            {"type": "approver", "name": "Marketing Lead", "detail": "Reviews mass email content"},
            {"type": "approver", "name": "Legal", "detail": "Compliance review for mass sends"},
            {"type": "approver", "name": "CEO", "detail": "Approves press releases"},
            {"type": "rule", "name": "Gmail mass email (500+)", "detail": "sequential → Marketing Lead → Legal"},
            {"type": "rule", "name": "Gmail mass email legal (10k+)", "detail": "all_of_n → Marketing + Legal + CEO"},
            {"type": "rule", "name": "Gmail press release", "detail": "specific → CEO"},
        ],
        "scenarios": [
            {
                "title": "Internal email (8 people) — auto",
                "description": "Small internal emails need no approval.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"subject": "Team lunch Friday", "recipient_count": 8, "audience_type": "internal"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Comms Agent", "sub": "send_email(8 recipients)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Gmail", "sub": "Send to 8 people"},
                ],
            },
            {
                "title": "Mass email (12,500) — sequential",
                "description": "Marketing lead reviews content, then legal checks compliance before sending.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"subject": "ApprovalKit 2.0 GA", "recipient_count": 12500, "audience_type": "subscribers"},
                "badge": "warning", "badgeLabel": "sequential",
                "flow": [
                    {"type": "agent", "label": "Comms Agent", "sub": "send_email(12,500 recipients)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: mass email"},
                    {"type": "approver", "label": "Marketing Lead", "sub": "Step 1 → Approve content"},
                    {"type": "approver", "label": "Legal", "sub": "Step 2 → Clear compliance"},
                    {"type": "action", "label": "Gmail", "sub": "Send to 12,500 subscribers"},
                ],
            },
            {
                "title": "Press release — PR → Legal → CEO",
                "description": "Three-step sequential chain. CEO is the final gatekeeper before going public.",
                "connection": "gmail-prod", "action": "press_release",
                "params": {"headline": "ApprovalKit Raises $8M Seed", "embargo_until": "2026-04-01T09:00Z", "distribution": "Business Wire, TechCrunch"},
                "badge": "danger", "badgeLabel": "sequential",
                "flow": [
                    {"type": "agent", "label": "Comms Agent", "sub": "issue_press_release(...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: press release"},
                    {"type": "approver", "label": "PR Manager", "sub": "Step 1 → Approve draft"},
                    {"type": "approver", "label": "Legal", "sub": "Step 2 → Legal clearance"},
                    {"type": "approver", "label": "CEO", "sub": "Step 3 → Final sign-off"},
                    {"type": "action", "label": "Distribution", "sub": "Business Wire + TechCrunch"},
                ],
            },
        ],
    },
]


@router.get("/agents")
async def list_demo_agents():
    """Return the demo agent catalog — frontend fetches this instead of hardcoding."""
    return DEMO_AGENTS


@router.post("/seed")
async def seed_demo_data(request: Request, agent_id: str | None = None, real_user_id: str | None = None, _ws: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    """
    Idempotently seed demo data. Pass ?agent_id=ecommerce to seed only
    one agent's data. Without agent_id, seeds everything.
    """
    report: dict[str, list[str]] = {
        "created": [], "skipped": []
    }

    # ── 1. Workspace (resolve per user) ────────────────────────────────────────
    user_sub = request.headers.get("X-User-Sub", "").strip()
    workspace = None
    if user_sub:
        ws_result = await db.execute(
            select(Workspace).where(Workspace.owner_auth0_sub == user_sub, Workspace.is_active.is_(True)).limit(1)
        )
        workspace = ws_result.scalar_one_or_none()
    if not workspace:
        ws_result = await db.execute(
            select(Workspace).where(Workspace.is_active.is_(True)).limit(1)
        )
        workspace = ws_result.scalar_one_or_none()
    if not workspace:
        import secrets as _secrets
        workspace = Workspace(
            name="Demo Workspace", is_active=True, auth0_tenant="demo",
            api_key=_secrets.token_urlsafe(32), hmac_secret=_secrets.token_hex(32),
            owner_auth0_sub=user_sub or None,
        )
        db.add(workspace)
        await db.flush()
        report["created"].append("workspace: Demo Workspace")
    ws_id = workspace.id

    # ── 2. Connections ────────────────────────────────────────────────────────
    existing_conns_result = await db.execute(select(ServiceConnection))
    existing_conn_slugs = {c.slug for c in existing_conns_result.scalars().all()}

    needed_slugs = set(AGENT_CONNECTIONS.get(agent_id, [])) if agent_id else None
    for conn_def in CONNECTIONS:
        if needed_slugs is not None and conn_def["slug"] not in needed_slugs:
            continue
        if conn_def["slug"] in existing_conn_slugs:
            report["skipped"].append(f"connection: {conn_def['slug']}")
            continue
        conn = ServiceConnection(
            workspace_id=ws_id,
            name=conn_def["name"],
            service=conn_def["service"],
            slug=conn_def["slug"],
            actions=conn_def["actions"],
            token_vault_connection_id=f"demo:{conn_def['slug']}",
        )
        db.add(conn)
        report["created"].append(f"connection: {conn_def['slug']}")

    await db.flush()

    # ── 3. Approvers ──────────────────────────────────────────────────────────
    existing_appr_result = await db.execute(select(Approver))
    existing_appr_ids = {a.auth0_user_id: a.id for a in existing_appr_result.scalars().all()}

    needed_roles = set(AGENT_APPROVERS.get(agent_id, [])) if agent_id else None
    approver_by_role: dict[str, uuid.UUID] = {}
    for appr_def in APPROVERS:
        if needed_roles is not None and appr_def["role"] not in needed_roles:
            if appr_def["auth0_user_id"] in existing_appr_ids:
                approver_by_role[appr_def["role"]] = existing_appr_ids[appr_def["auth0_user_id"]]
            # Also check by real_user_id
            if real_user_id and real_user_id in existing_appr_ids:
                approver_by_role[appr_def["role"]] = existing_appr_ids[real_user_id]
            continue
        uid = real_user_id or appr_def["auth0_user_id"]
        if uid in existing_appr_ids:
            approver_by_role[appr_def["role"]] = existing_appr_ids[uid]
            report["skipped"].append(f"approver: {appr_def['name']}")
            continue
        appr = Approver(
            workspace_id=ws_id,
            name=appr_def["name"],
            email=appr_def["email"],
            auth0_user_id=uid,
            notify_channel=["guardian_push"],
            urgent_channel=["guardian_push"],
        )
        db.add(appr)
        await db.flush()
        approver_by_role[appr_def["role"]] = appr.id
        report["created"].append(f"approver: {appr_def['name']}")

    # ── 4. Rules ──────────────────────────────────────────────────────────────
    existing_rules_result = await db.execute(select(Rule).where(Rule.workspace_id == ws_id))
    existing_rule_names = {r.name for r in existing_rules_result.scalars().all()}

    rule_prefixes = AGENT_RULES.get(agent_id, []) if agent_id else None
    for rule_def in _build_rules(approver_by_role):
        if rule_prefixes is not None:
            if not any(rule_def["name"].replace("[Demo] ", "").startswith(p) for p in rule_prefixes):
                continue
        if rule_def["name"] in existing_rule_names:
            report["skipped"].append(f"rule: {rule_def['name']}")
            continue

        roles = rule_def.pop("approver_roles", [])
        conditions = rule_def.pop("conditions", [])

        rule = Rule(
            workspace_id=ws_id,
            name=rule_def["name"],
            connection=rule_def["connection"],
            action=rule_def["action"],
            model=rule_def["model"],
            timeout_seconds=rule_def.get("timeout_seconds", 300),
            on_timeout=TimeoutAction.BLOCK,
            context_template=rule_def.get("context_template"),
            conditions=conditions,
            partial_approval=rule_def.get("partial_approval", False),
            k_value=rule_def.get("k_value"),
            priority=rule_def.get("priority", 0),
            is_active=True,
        )
        db.add(rule)
        await db.flush()

        for order, role in enumerate(roles):
            appr_id = approver_by_role.get(role)
            if appr_id:
                ra = RuleApprover(rule_id=rule.id, approver_id=appr_id, order=order)
                db.add(ra)

        report["created"].append(f"rule: {rule_def['name']}")

    await db.commit()

    return {
        "status": "ok",
        "created_count": len(report["created"]),
        "skipped_count": len(report["skipped"]),
        "created": report["created"],
        "skipped": report["skipped"],
    }


@router.delete("/seed")
async def clear_demo_data(workspace: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    """Remove all demo resources (names start with '[Demo]')."""

    rules_result = await db.execute(
        select(Rule).where(
            Rule.workspace_id == workspace.id,
            Rule.name.like("[Demo]%"),
        )
    )
    rules = rules_result.scalars().all()
    deleted = 0
    for rule in rules:
        await db.delete(rule)
        deleted += 1

    approvers_result = await db.execute(
        select(Approver).where(
            Approver.workspace_id == workspace.id,
            Approver.email.like("%@demo.approvalkit.io"),
        )
    )
    for appr in approvers_result.scalars().all():
        await db.delete(appr)
        deleted += 1

    await db.commit()
    return {"status": "ok", "deleted": deleted}

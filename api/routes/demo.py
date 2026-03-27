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
     "actions": ["charge", "refund", "payout", "wire_transfer", "vendor_payment", "subscription", "credit"]},
    {"name": "Slack Production",   "service": "slack",  "slug": "slack-prod",
     "actions": ["send_message"]},
    {"name": "Gmail Production",   "service": "gmail",  "slug": "gmail-prod",
     "actions": ["send_email", "press_release"]},
    {"name": "GitHub Production",  "service": "github", "slug": "github-prod",
     "actions": ["add_member", "remove_member", "deploy", "rollback", "merge_pr", "lock_repo", "revoke_tokens"]},
    {"name": "GitHub Main",        "service": "github", "slug": "github-main",
     "actions": ["deploy", "rollback", "merge_pr"]},
    {"name": "AWS Lab",            "service": "aws",    "slug": "aws-lab",
     "actions": ["provision_compute"]},
    {"name": "arXiv",              "service": "arxiv",  "slug": "arxiv",
     "actions": ["submit_paper"]},
    {"name": "Salesforce Production", "service": "salesforce", "slug": "salesforce-prod",
     "actions": ["update_case", "create_ticket", "log_complaint"]},
    {"name": "PagerDuty Production", "service": "pagerduty", "slug": "pagerduty-prod",
     "actions": ["create_incident", "notify_oncall"]},
    {"name": "Google Calendar",    "service": "google_calendar", "slug": "calendar-prod",
     "actions": ["create_event", "block_time"]},
    {"name": "Google Drive",       "service": "google_drive", "slug": "gdrive-prod",
     "actions": ["share_file", "create_folder"]},
    {"name": "Google Sheets",      "service": "google_sheets", "slug": "gsheets-prod",
     "actions": ["update_sheet", "create_sheet"]},
    {"name": "Dropbox Production", "service": "dropbox", "slug": "dropbox-prod",
     "actions": ["upload_file", "share_folder"]},
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
    # ── New roles for 36 demo agents ──
    {"name": "Security Lead",    "email": "security_lead@demo.approvalkit.io",
     "auth0_user_id": "demo|security_lead",    "role": "security_lead"},
    {"name": "Compliance Officer","email": "compliance@demo.approvalkit.io",
     "auth0_user_id": "demo|compliance",       "role": "compliance_officer"},
    {"name": "DBA",              "email": "dba@demo.approvalkit.io",
     "auth0_user_id": "demo|dba",             "role": "dba"},
    {"name": "Sustainability Officer","email": "sustainability@demo.approvalkit.io",
     "auth0_user_id": "demo|sustainability",   "role": "sustainability_officer"},
    {"name": "On-Call Engineer", "email": "oncall@demo.approvalkit.io",
     "auth0_user_id": "demo|oncall",          "role": "oncall_engineer"},
    {"name": "Doctor",           "email": "doctor@demo.approvalkit.io",
     "auth0_user_id": "demo|doctor",          "role": "doctor"},
    {"name": "Patient Rep",      "email": "patient_rep@demo.approvalkit.io",
     "auth0_user_id": "demo|patient_rep",     "role": "patient_rep"},
    {"name": "Chief Doctor",     "email": "chief_doctor@demo.approvalkit.io",
     "auth0_user_id": "demo|chief_doctor",    "role": "chief_doctor"},
    {"name": "Pharmacist",       "email": "pharmacist@demo.approvalkit.io",
     "auth0_user_id": "demo|pharmacist",      "role": "pharmacist"},
    {"name": "Ethics Board",     "email": "ethics@demo.approvalkit.io",
     "auth0_user_id": "demo|ethics_board",    "role": "ethics_board"},
    {"name": "Teacher",          "email": "teacher@demo.approvalkit.io",
     "auth0_user_id": "demo|teacher",         "role": "teacher"},
    {"name": "Department Head",  "email": "dept_head@demo.approvalkit.io",
     "auth0_user_id": "demo|dept_head",       "role": "department_head"},
    {"name": "Scholarship Committee","email": "scholarship@demo.approvalkit.io",
     "auth0_user_id": "demo|scholarship",     "role": "scholarship_committee"},
    {"name": "Rector",           "email": "rector@demo.approvalkit.io",
     "auth0_user_id": "demo|rector",          "role": "rector"},
    {"name": "Privacy Officer",  "email": "privacy@demo.approvalkit.io",
     "auth0_user_id": "demo|privacy",         "role": "privacy_officer"},
    {"name": "Building Manager", "email": "building_mgr@demo.approvalkit.io",
     "auth0_user_id": "demo|building_mgr",    "role": "building_manager"},
    {"name": "Property Owner",   "email": "property_owner@demo.approvalkit.io",
     "auth0_user_id": "demo|property_owner",  "role": "property_owner"},
    {"name": "Property Manager", "email": "property_mgr@demo.approvalkit.io",
     "auth0_user_id": "demo|property_mgr",    "role": "property_manager"},
    {"name": "Moderator",        "email": "moderator@demo.approvalkit.io",
     "auth0_user_id": "demo|moderator",       "role": "moderator"},
    {"name": "Senior Moderator", "email": "sr_moderator@demo.approvalkit.io",
     "auth0_user_id": "demo|sr_moderator",    "role": "senior_moderator"},
    {"name": "Environmental Officer","email": "env_officer@demo.approvalkit.io",
     "auth0_user_id": "demo|env_officer",     "role": "environmental_officer"},
    {"name": "Board Member",     "email": "board@demo.approvalkit.io",
     "auth0_user_id": "demo|board",           "role": "board"},
    {"name": "CS Agent",         "email": "cs_agent_v2@demo.approvalkit.io",
     "auth0_user_id": "demo|cs_agent_v2",     "role": "cs_agent_v2"},
    {"name": "External Board",   "email": "ext_board@demo.approvalkit.io",
     "auth0_user_id": "demo|ext_board",       "role": "external_board"},
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

        # ── Invoice Agent ────────────────────────────────────────────────────
        {
            "name": "[Demo] Invoice — medium ($1000-$5000)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Invoice ${amount_usd} to {customer} — {description}",
            "conditions": [c("type", "eq", "invoice"), c("amount_usd", "gte", 1000), c("amount_usd", "lt", 5000)],
            "approver_roles": ["cfo"],
            "priority": 15,
        },
        {
            "name": "[Demo] Invoice — large ($5000+)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "LARGE invoice ${amount_usd} to {customer}",
            "conditions": [c("type", "eq", "invoice"), c("amount_usd", "gte", 5000)],
            "approver_roles": ["cfo", "legal"],
            "priority": 25,
        },
        {
            "name": "[Demo] Legal collection",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "Legal collection for {customer}: ${amount_usd}",
            "conditions": [c("type", "eq", "legal_collection")],
            "approver_roles": ["cfo", "legal"],
            "priority": 30,
        },

        # ── Expense Agent ────────────────────────────────────────────────────
        {
            "name": "[Demo] Expense — medium ($500-$5000)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Expense ${amount_usd} — {category}: {description}",
            "conditions": [c("type", "eq", "expense"), c("amount_usd", "gte", 500), c("amount_usd", "lt", 5000)],
            "approver_roles": ["manager"],
            "priority": 15,
        },
        {
            "name": "[Demo] Expense — large ($5000+)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "LARGE expense ${amount_usd} — {category}: {description}",
            "conditions": [c("type", "eq", "expense"), c("amount_usd", "gte", 5000)],
            "approver_roles": ["manager", "cfo"],
            "priority": 25,
        },

        # ── Subscription Agent ───────────────────────────────────────────────
        {
            "name": "[Demo] Enterprise pricing",
            "connection": "stripe-prod", "action": "subscription",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Enterprise plan for {customer}: ${amount_usd}/mo",
            "conditions": [c("type", "eq", "enterprise_pricing")],
            "approver_roles": ["ceo"],
            "priority": 20,
        },
        {
            "name": "[Demo] Bulk cancellation",
            "connection": "stripe-prod", "action": "subscription",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "Bulk cancel {count} subscriptions",
            "conditions": [c("type", "eq", "bulk_cancel")],
            "approver_roles": ["cfo", "manager"],
            "priority": 30,
        },

        # ── Vendor Payment Agent ─────────────────────────────────────────────
        {
            "name": "[Demo] Vendor payment — medium ($1k-$10k)",
            "connection": "stripe-prod", "action": "vendor_payment",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Vendor payment ${amount_usd} to {vendor_name}",
            "conditions": [c("amount_usd", "gte", 1000), c("amount_usd", "lt", 10000), c("is_new_vendor", "eq", False)],
            "approver_roles": ["finance"],
            "priority": 15,
        },
        {
            "name": "[Demo] Vendor payment — large ($10k+)",
            "connection": "stripe-prod", "action": "vendor_payment",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "LARGE vendor payment ${amount_usd} to {vendor_name}",
            "conditions": [c("amount_usd", "gte", 10000), c("is_new_vendor", "eq", False)],
            "approver_roles": ["cfo", "ceo"],
            "priority": 25,
        },

        # ── Churn Prevention Agent ───────────────────────────────────────────
        {
            "name": "[Demo] Retention discount — medium (11-30%)",
            "connection": "stripe-prod", "action": "credit",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Retention {discount_pct}% discount for {customer}",
            "conditions": [c("discount_pct", "gte", 11), c("discount_pct", "lte", 30)],
            "approver_roles": ["manager"],
            "priority": 15,
        },
        {
            "name": "[Demo] Custom package",
            "connection": "stripe-prod", "action": "credit",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Custom package for {customer}: {description}",
            "conditions": [c("type", "eq", "custom_package")],
            "approver_roles": ["ceo"],
            "priority": 25,
        },
        {
            "name": "[Demo] Enterprise custom pricing",
            "connection": "stripe-prod", "action": "credit",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "Enterprise custom ${amount_usd}/yr for {customer}",
            "conditions": [c("type", "eq", "enterprise_custom")],
            "approver_roles": ["ceo", "cfo"],
            "priority": 35,
        },

        # ── Carbon Credit Agent ──────────────────────────────────────────────
        {
            "name": "[Demo] Carbon credits — large ($10k-$50k)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Carbon credits: {quantity} tons at ${price_per_ton}/ton (${amount_usd})",
            "conditions": [c("type", "eq", "carbon_credit"), c("amount_usd", "gte", 10000), c("amount_usd", "lt", 50000)],
            "approver_roles": ["sustainability_officer"],
            "priority": 20,
        },
        {
            "name": "[Demo] Carbon forward contract",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "Carbon forward contract ${amount_usd} — {years}yr",
            "conditions": [c("type", "eq", "carbon_forward")],
            "approver_roles": ["cfo", "sustainability_officer"],
            "priority": 35,
        },

        # ── Release Manager Agent ────────────────────────────────────────────
        {
            "name": "[Demo] Production deploy",
            "connection": "github-main", "action": "deploy",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Deploy {ref} to {environment}",
            "conditions": [c("environment", "eq", "production")],
            "approver_roles": ["maintainer"],
            "priority": 20,
        },
        {
            "name": "[Demo] Hotfix deploy (blackout)",
            "connection": "github-main", "action": "deploy",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 120,
            "context_template": "HOTFIX deploy {ref} to {environment}",
            "conditions": [c("type", "eq", "hotfix")],
            "approver_roles": ["oncall_engineer"],
            "priority": 40,
        },
        {
            "name": "[Demo] Production rollback",
            "connection": "github-main", "action": "rollback",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 120,
            "context_template": "Rollback {env} to {version} — {reason}",
            "conditions": [c("env", "eq", "production")],
            "approver_roles": ["lead_engineer"],
            "priority": 30,
        },

        # ── Security Incident Agent ──────────────────────────────────────────
        {
            "name": "[Demo] Lock repository",
            "connection": "github-prod", "action": "lock_repo",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 300,
            "context_template": "Lock repo {repo} — {reason}",
            "conditions": [],
            "approver_roles": ["security_lead"],
            "priority": 20,
        },
        {
            "name": "[Demo] Revoke production access",
            "connection": "github-prod", "action": "revoke_tokens",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 300,
            "context_template": "Revoke all tokens for {scope} — {reason}",
            "conditions": [],
            "approver_roles": ["cto", "security_lead"],
            "priority": 40,
        },

        # ── Dependency Update Agent ──────────────────────────────────────────
        {
            "name": "[Demo] Minor dependency update",
            "connection": "github-prod", "action": "merge_pr",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Update {package} {from_version} → {to_version} (minor)",
            "conditions": [c("update_type", "eq", "minor")],
            "approver_roles": ["lead_engineer"],
            "priority": 15,
        },
        {
            "name": "[Demo] Major dependency update",
            "connection": "github-prod", "action": "merge_pr",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "BREAKING: {package} {from_version} → {to_version} (major)",
            "conditions": [c("update_type", "eq", "major")],
            "approver_roles": ["lead_engineer", "maintainer", "cto"],
            "priority": 30,
        },

        # ── Database Migration Agent ─────────────────────────────────────────
        {
            "name": "[Demo] Staging migration",
            "connection": "github-prod", "action": "deploy",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Migration on staging: {migration_name}",
            "conditions": [c("type", "eq", "migration"), c("env", "eq", "staging")],
            "approver_roles": ["dba"],
            "priority": 15,
        },
        {
            "name": "[Demo] Production migration",
            "connection": "github-prod", "action": "deploy",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "PROD migration: {migration_name} — {description}",
            "conditions": [c("type", "eq", "migration"), c("env", "eq", "production")],
            "approver_roles": ["dba", "cto"],
            "priority": 35,
        },

        # ── API Key Rotation Agent ───────────────────────────────────────────
        {
            "name": "[Demo] Emergency key rotation",
            "connection": "github-prod", "action": "deploy",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 180,
            "context_template": "EMERGENCY rotate {service} API key — {reason}",
            "conditions": [c("type", "eq", "key_rotation"), c("urgency", "eq", "emergency")],
            "approver_roles": ["security_lead"],
            "priority": 40,
        },
        {
            "name": "[Demo] Third-party key rotation",
            "connection": "github-prod", "action": "deploy",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "Rotate 3rd-party key: {service} ({provider})",
            "conditions": [c("type", "eq", "key_rotation"), c("scope", "eq", "third_party")],
            "approver_roles": ["security_lead", "cto"],
            "priority": 30,
        },

        # ── Compliance Audit Agent ───────────────────────────────────────────
        {
            "name": "[Demo] Violation report",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Compliance violation: {framework} — {description}",
            "conditions": [c("type", "eq", "violation_report")],
            "approver_roles": ["compliance_officer"],
            "priority": 25,
        },
        {
            "name": "[Demo] Regulatory filing",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "Regulatory filing to {authority}: {subject}",
            "conditions": [c("type", "eq", "regulatory_filing")],
            "approver_roles": ["legal", "ceo"],
            "priority": 40,
        },

        # ── Recruitment Agent ────────────────────────────────────────────────
        {
            "name": "[Demo] Salary package",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "Salary package for {candidate}: ${salary} + {equity}",
            "conditions": [c("type", "eq", "salary_package")],
            "approver_roles": ["hr_manager", "cfo"],
            "priority": 25,
        },

        # ── Access Provisioning Agent ────────────────────────────────────────
        {
            "name": "[Demo] Standard access",
            "connection": "github-prod", "action": "add_member",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Grant {access_level} access to {username}",
            "conditions": [c("access_level", "eq", "standard")],
            "approver_roles": ["it_manager"],
            "priority": 10,
        },
        {
            "name": "[Demo] Admin access",
            "connection": "github-prod", "action": "add_member",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Grant ADMIN access to {username}",
            "conditions": [c("access_level", "eq", "admin")],
            "approver_roles": ["cto"],
            "priority": 25,
        },
        {
            "name": "[Demo] Financial system access",
            "connection": "github-prod", "action": "add_member",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "Grant financial system access to {username}",
            "conditions": [c("access_level", "eq", "financial")],
            "approver_roles": ["cfo", "cto"],
            "priority": 35,
        },

        # ── Leave Management Agent ───────────────────────────────────────────
        {
            "name": "[Demo] Week leave (3-5 days)",
            "connection": "calendar-prod", "action": "block_time",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Leave request: {employee} — {days} days ({start_date})",
            "conditions": [c("days", "gte", 3), c("days", "lte", 5)],
            "approver_roles": ["manager"],
            "priority": 15,
        },
        {
            "name": "[Demo] Long leave (20+ days)",
            "connection": "calendar-prod", "action": "block_time",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Long leave: {employee} — {days} days",
            "conditions": [c("days", "gte", 20)],
            "approver_roles": ["hr_manager"],
            "priority": 25,
        },
        {
            "name": "[Demo] Critical period leave",
            "connection": "calendar-prod", "action": "block_time",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "Leave during critical period: {employee} — {reason}",
            "conditions": [c("is_critical_period", "eq", True)],
            "approver_roles": ["manager", "ceo"],
            "priority": 40,
        },

        # ── Contractor Onboarding Agent ──────────────────────────────────────
        {
            "name": "[Demo] Contractor payment agreement",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Contractor agreement: {contractor} — ${amount_usd}/mo",
            "conditions": [c("type", "eq", "contractor_agreement")],
            "approver_roles": ["legal"],
            "priority": 20,
        },
        {
            "name": "[Demo] Large contractor ($10k+)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "Large contract ${amount_usd} — {contractor}",
            "conditions": [c("type", "eq", "contractor_agreement"), c("amount_usd", "gte", 10000)],
            "approver_roles": ["legal", "ceo"],
            "priority": 30,
        },

        # ── Performance Review Agent ─────────────────────────────────────────
        {
            "name": "[Demo] Promotion recommendation",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "Promote {employee} to {new_title}",
            "conditions": [c("type", "eq", "promotion")],
            "approver_roles": ["hr_manager", "manager"],
            "priority": 20,
        },
        {
            "name": "[Demo] Salary increase",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "Salary increase {employee}: ${current} → ${new_salary}",
            "conditions": [c("type", "eq", "salary_increase")],
            "approver_roles": ["hr_manager", "cfo"],
            "priority": 25,
        },

        # ── Support Escalation Agent ─────────────────────────────────────────
        {
            "name": "[Demo] VIP complaint",
            "connection": "salesforce-prod", "action": "update_case",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 300,
            "context_template": "VIP complaint from {customer}: {subject}",
            "conditions": [c("customer_tier", "eq", "vip")],
            "approver_roles": ["cs_manager"],
            "priority": 20,
        },
        {
            "name": "[Demo] Large compensation ($1000+)",
            "connection": "stripe-prod", "action": "refund",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "Compensation ${amount_usd} for {customer} — {reason}",
            "conditions": [c("type", "eq", "compensation"), c("amount_usd", "gte", 1000)],
            "approver_roles": ["cfo", "legal"],
            "priority": 35,
        },

        # ── Account Takeover Agent ───────────────────────────────────────────
        {
            "name": "[Demo] Freeze account",
            "connection": "salesforce-prod", "action": "update_case",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 180,
            "context_template": "Freeze account {account_id} — {reason}",
            "conditions": [c("type", "eq", "freeze_account")],
            "approver_roles": ["security_lead"],
            "priority": 30,
        },
        {
            "name": "[Demo] Permanent ban",
            "connection": "salesforce-prod", "action": "update_case",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "Permanent ban: {account_id} — {reason}",
            "conditions": [c("type", "eq", "permanent_ban")],
            "approver_roles": ["security_lead", "legal"],
            "priority": 40,
        },

        # ── SLA Breach Agent ─────────────────────────────────────────────────
        {
            "name": "[Demo] SLA credit (<$5000)",
            "connection": "stripe-prod", "action": "credit",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "SLA credit ${amount_usd} for {customer}",
            "conditions": [c("type", "eq", "sla_credit"), c("amount_usd", "lt", 5000)],
            "approver_roles": ["cs_manager"],
            "priority": 15,
        },
        {
            "name": "[Demo] SLA compensation ($5000+)",
            "connection": "stripe-prod", "action": "credit",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "SLA compensation ${amount_usd} for {customer}",
            "conditions": [c("type", "eq", "sla_credit"), c("amount_usd", "gte", 5000)],
            "approver_roles": ["cfo", "legal"],
            "priority": 30,
        },

        # ── Patient Data Sharing Agent ───────────────────────────────────────
        {
            "name": "[Demo] Share with external clinic",
            "connection": "gdrive-prod", "action": "share_file",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Share {patient_id} records with {clinic}",
            "conditions": [c("recipient_type", "eq", "external_clinic")],
            "approver_roles": ["doctor"],
            "priority": 20,
        },
        {
            "name": "[Demo] Share with insurance",
            "connection": "gdrive-prod", "action": "share_file",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "Share {patient_id} records with {insurance_company}",
            "conditions": [c("recipient_type", "eq", "insurance")],
            "approver_roles": ["patient_rep", "doctor"],
            "priority": 35,
        },

        # ── Medical Supply Agent ─────────────────────────────────────────────
        {
            "name": "[Demo] Medical equipment ($1k-$20k)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Medical supply: {item} — ${amount_usd}",
            "conditions": [c("type", "eq", "medical_supply"), c("amount_usd", "gte", 1000), c("amount_usd", "lt", 20000)],
            "approver_roles": ["chief_doctor"],
            "priority": 20,
        },
        {
            "name": "[Demo] Medical device ($20k+)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "Medical device purchase: {item} — ${amount_usd}",
            "conditions": [c("type", "eq", "medical_supply"), c("amount_usd", "gte", 20000)],
            "approver_roles": ["chief_doctor", "cfo"],
            "priority": 35,
        },

        # ── Prescription Refill Agent ────────────────────────────────────────
        {
            "name": "[Demo] Controlled substance refill",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Refill {medication} for {patient}",
            "conditions": [c("type", "eq", "controlled_refill")],
            "approver_roles": ["doctor"],
            "priority": 25,
        },
        {
            "name": "[Demo] Dosage change",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "Dosage change: {medication} {old_dosage} → {new_dosage} for {patient}",
            "conditions": [c("type", "eq", "dosage_change")],
            "approver_roles": ["doctor", "pharmacist"],
            "priority": 30,
        },

        # ── Research Data Agent ──────────────────────────────────────────────
        {
            "name": "[Demo] Patient-level data access",
            "connection": "gdrive-prod", "action": "share_file",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 900,
            "context_template": "Access patient data for study {study_id}",
            "conditions": [c("data_type", "eq", "patient_level")],
            "approver_roles": ["ethics_board"],
            "priority": 25,
        },
        {
            "name": "[Demo] External research data share",
            "connection": "gdrive-prod", "action": "share_file",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "Share research data with {institution}",
            "conditions": [c("data_type", "eq", "external_share")],
            "approver_roles": ["ethics_board", "chief_doctor"],
            "priority": 40,
        },

        # ── Grade Override Agent ─────────────────────────────────────────────
        {
            "name": "[Demo] Grade appeal",
            "connection": "gsheets-prod", "action": "update_sheet",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Grade appeal: {student} — {course} {current_grade} → {new_grade}",
            "conditions": [c("type", "eq", "grade_appeal")],
            "approver_roles": ["teacher"],
            "priority": 20,
        },
        {
            "name": "[Demo] Final grade override",
            "connection": "gsheets-prod", "action": "update_sheet",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "Final override: {student} — {course} → {new_grade}",
            "conditions": [c("type", "eq", "final_override")],
            "approver_roles": ["teacher", "department_head"],
            "priority": 35,
        },

        # ── Scholarship Agent ────────────────────────────────────────────────
        {
            "name": "[Demo] Scholarship award (<$10k)",
            "connection": "stripe-prod", "action": "payout",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 600,
            "context_template": "Scholarship ${amount_usd} for {student} — {type}",
            "conditions": [c("type", "eq", "scholarship"), c("amount_usd", "lt", 10000)],
            "approver_roles": ["scholarship_committee"],
            "priority": 20,
        },
        {
            "name": "[Demo] Full scholarship",
            "connection": "stripe-prod", "action": "payout",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "Full scholarship ${amount_usd}/yr for {student}",
            "conditions": [c("type", "eq", "full_scholarship")],
            "approver_roles": ["rector", "scholarship_committee"],
            "priority": 35,
        },

        # ── Research Grant Agent ─────────────────────────────────────────────
        {
            "name": "[Demo] Grant spend (<$5k)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Grant spend ${amount_usd} — {purpose}",
            "conditions": [c("type", "eq", "grant"), c("amount_usd", "lt", 5000)],
            "approver_roles": ["department_head"],
            "priority": 15,
        },
        {
            "name": "[Demo] Grant spend ($5k-$50k)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Grant spend ${amount_usd} — {purpose}",
            "conditions": [c("type", "eq", "grant"), c("amount_usd", "gte", 5000), c("amount_usd", "lt", 50000)],
            "approver_roles": ["rector"],
            "priority": 25,
        },
        {
            "name": "[Demo] Grant spend ($50k+)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "LARGE grant ${amount_usd} — {purpose}",
            "conditions": [c("type", "eq", "grant"), c("amount_usd", "gte", 50000)],
            "approver_roles": ["rector", "external_board"],
            "priority": 40,
        },

        # ── Contract Signing Agent ───────────────────────────────────────────
        {
            "name": "[Demo] Service agreement",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Service agreement with {party}: {subject}",
            "conditions": [c("type", "eq", "service_agreement")],
            "approver_roles": ["legal"],
            "priority": 20,
        },
        {
            "name": "[Demo] Partnership agreement",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "Partnership agreement with {party}",
            "conditions": [c("type", "eq", "partnership")],
            "approver_roles": ["ceo", "legal"],
            "priority": 35,
        },

        # ── GDPR Request Agent ───────────────────────────────────────────────
        {
            "name": "[Demo] GDPR single delete",
            "connection": "github-prod", "action": "deploy",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Delete data for {user_email} per GDPR request",
            "conditions": [c("type", "eq", "gdpr_delete")],
            "approver_roles": ["privacy_officer"],
            "priority": 20,
        },
        {
            "name": "[Demo] GDPR bulk delete",
            "connection": "github-prod", "action": "deploy",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "Bulk GDPR delete: {count} records",
            "conditions": [c("type", "eq", "gdpr_bulk_delete")],
            "approver_roles": ["cto", "privacy_officer"],
            "priority": 35,
        },

        # ── IP Filing Agent ──────────────────────────────────────────────────
        {
            "name": "[Demo] Domestic patent filing",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 900,
            "context_template": "Patent filing: {title} (domestic)",
            "conditions": [c("type", "eq", "domestic_filing")],
            "approver_roles": ["legal"],
            "priority": 25,
        },
        {
            "name": "[Demo] International patent (PCT)",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "International patent: {title} — PCT",
            "conditions": [c("type", "eq", "international_filing")],
            "approver_roles": ["ceo", "legal"],
            "priority": 40,
        },

        # ── Maintenance Request Agent ────────────────────────────────────────
        {
            "name": "[Demo] Maintenance — medium ($500-$5k)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Maintenance: {description} — ${amount_usd}",
            "conditions": [c("type", "eq", "maintenance"), c("amount_usd", "gte", 500), c("amount_usd", "lt", 5000)],
            "approver_roles": ["building_manager"],
            "priority": 15,
        },
        {
            "name": "[Demo] Maintenance — large ($5k+)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "Major maintenance: {description} — ${amount_usd}",
            "conditions": [c("type", "eq", "maintenance"), c("amount_usd", "gte", 5000)],
            "approver_roles": ["building_manager", "property_owner"],
            "priority": 30,
        },

        # ── Tenant Screening Agent ───────────────────────────────────────────
        {
            "name": "[Demo] Eviction history review",
            "connection": "salesforce-prod", "action": "create_ticket",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Screen applicant {applicant}: eviction history",
            "conditions": [c("check_type", "eq", "eviction_history")],
            "approver_roles": ["property_manager"],
            "priority": 20,
        },
        {
            "name": "[Demo] Criminal record check",
            "connection": "salesforce-prod", "action": "create_ticket",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "Screen applicant {applicant}: criminal record",
            "conditions": [c("check_type", "eq", "criminal_check")],
            "approver_roles": ["property_manager", "legal"],
            "priority": 30,
        },

        # ── Content Moderation Agent ─────────────────────────────────────────
        {
            "name": "[Demo] Suspicious content review",
            "connection": "slack-prod", "action": "send_message",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Review content: {content_id} — {reason}",
            "conditions": [c("type", "eq", "suspicious_content")],
            "approver_roles": ["moderator"],
            "priority": 15,
        },
        {
            "name": "[Demo] Account ban",
            "connection": "slack-prod", "action": "send_message",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "Ban account {account_id} — {reason}",
            "conditions": [c("type", "eq", "account_ban")],
            "approver_roles": ["senior_moderator", "legal"],
            "priority": 35,
        },

        # ── Licensing Agent ──────────────────────────────────────────────────
        {
            "name": "[Demo] Commercial license",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Commercial license for {licensee}: ${amount_usd}",
            "conditions": [c("type", "eq", "commercial_license")],
            "approver_roles": ["legal"],
            "priority": 20,
        },
        {
            "name": "[Demo] Major media deal ($100k+)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "Major deal ${amount_usd} with {licensee}",
            "conditions": [c("type", "eq", "major_deal"), c("amount_usd", "gte", 100000)],
            "approver_roles": ["ceo", "legal"],
            "priority": 40,
        },

        # ── Environmental Incident Agent ─────────────────────────────────────
        {
            "name": "[Demo] Major environmental incident",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 300,
            "context_template": "MAJOR incident: {incident_type} at {location}",
            "conditions": [c("type", "eq", "major_incident")],
            "approver_roles": ["ceo", "environmental_officer"],
            "priority": 50,
        },

        # ── Renewable Energy Agent ───────────────────────────────────────────
        {
            "name": "[Demo] Energy purchase ($10k-$100k)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Energy purchase: {quantity} MWh — ${amount_usd}",
            "conditions": [c("type", "eq", "energy_purchase"), c("amount_usd", "gte", 10000), c("amount_usd", "lt", 100000)],
            "approver_roles": ["cfo"],
            "priority": 20,
        },
        {
            "name": "[Demo] Long-term PPA",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "PPA agreement: {years}yr ${amount_usd}",
            "conditions": [c("type", "eq", "ppa_agreement")],
            "approver_roles": ["ceo", "cfo"],
            "priority": 40,
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
    # ── New agents ──
    "invoice": ["Invoice", "Legal collection"],
    "expense": ["Expense"],
    "subscription": ["Enterprise pricing", "Bulk cancellation"],
    "vendor_payment": ["Vendor payment"],
    "churn_prevention": ["Retention discount", "Custom package", "Enterprise custom"],
    "carbon_credit": ["Carbon credits", "Carbon forward"],
    "release_manager": ["Production deploy", "Hotfix deploy", "Production rollback"],
    "security_incident": ["Lock repository", "Revoke production"],
    "dependency_update": ["Minor dependency", "Major dependency"],
    "db_migration": ["Staging migration", "Production migration"],
    "api_key_rotation": ["Emergency key", "Third-party key"],
    "compliance_audit": ["Violation report", "Regulatory filing"],
    "recruitment": ["Salary package", "Gmail offer", "Gmail termination"],
    "access_provisioning": ["Standard access", "Admin access", "Financial system"],
    "leave_management": ["Week leave", "Long leave", "Critical period"],
    "contractor_onboarding": ["Contractor payment", "Large contractor"],
    "performance_review": ["Promotion recommendation", "Salary increase"],
    "support_escalation": ["VIP complaint", "Large compensation"],
    "account_takeover": ["Freeze account", "Permanent ban"],
    "sla_breach": ["SLA credit", "SLA compensation"],
    "patient_data": ["Share with external", "Share with insurance"],
    "medical_supply": ["Medical equipment", "Medical device"],
    "prescription_refill": ["Controlled substance", "Dosage change"],
    "research_data": ["Patient-level data", "External research"],
    "grade_override": ["Grade appeal", "Final grade"],
    "scholarship": ["Scholarship award", "Full scholarship"],
    "research_grant": ["Grant spend"],
    "contract_signing": ["Service agreement", "Partnership agreement"],
    "gdpr_request": ["GDPR single", "GDPR bulk"],
    "ip_filing": ["Domestic patent", "International patent"],
    "maintenance_request": ["Maintenance"],
    "tenant_screening": ["Eviction history", "Criminal record"],
    "content_moderation": ["Suspicious content", "Account ban"],
    "licensing": ["Commercial license", "Major media"],
    "environmental_incident": ["Major environmental"],
    "renewable_energy": ["Energy purchase", "Long-term PPA"],
}

# Agent → required connections
AGENT_CONNECTIONS = {
    "ecommerce": ["stripe-prod", "slack-prod"],
    "hr": ["gmail-prod", "github-prod"],
    "devops": ["github-main"],
    "opensource": ["github-main", "stripe-prod"],
    "research": ["aws-lab", "arxiv"],
    "fintech": ["stripe-prod"],
    # ── New agents ──
    "invoice": ["stripe-prod", "gmail-prod", "salesforce-prod"],
    "expense": ["stripe-prod", "slack-prod", "gmail-prod"],
    "subscription": ["stripe-prod", "slack-prod", "gmail-prod"],
    "vendor_payment": ["stripe-prod", "slack-prod", "gmail-prod"],
    "churn_prevention": ["stripe-prod", "salesforce-prod", "gmail-prod"],
    "carbon_credit": ["stripe-prod", "slack-prod", "gmail-prod"],
    "release_manager": ["github-main", "slack-prod", "pagerduty-prod"],
    "security_incident": ["github-prod", "slack-prod", "pagerduty-prod"],
    "dependency_update": ["github-prod", "slack-prod"],
    "db_migration": ["github-prod", "slack-prod"],
    "api_key_rotation": ["github-prod", "slack-prod", "gmail-prod"],
    "compliance_audit": ["gmail-prod", "slack-prod", "salesforce-prod"],
    "recruitment": ["gmail-prod", "slack-prod", "github-prod", "calendar-prod"],
    "access_provisioning": ["github-prod", "slack-prod", "gmail-prod"],
    "leave_management": ["slack-prod", "calendar-prod", "gmail-prod"],
    "contractor_onboarding": ["gmail-prod", "stripe-prod", "github-prod"],
    "performance_review": ["gmail-prod", "slack-prod", "stripe-prod"],
    "support_escalation": ["salesforce-prod", "slack-prod", "gmail-prod", "stripe-prod"],
    "account_takeover": ["salesforce-prod", "slack-prod", "gmail-prod"],
    "sla_breach": ["stripe-prod", "slack-prod", "gmail-prod"],
    "patient_data": ["gdrive-prod", "gmail-prod", "slack-prod"],
    "medical_supply": ["stripe-prod", "slack-prod", "gmail-prod"],
    "prescription_refill": ["gmail-prod", "slack-prod"],
    "research_data": ["gdrive-prod", "gmail-prod", "slack-prod"],
    "grade_override": ["gmail-prod", "slack-prod", "gsheets-prod"],
    "scholarship": ["gmail-prod", "stripe-prod", "slack-prod"],
    "research_grant": ["stripe-prod", "gmail-prod", "slack-prod"],
    "contract_signing": ["gmail-prod", "slack-prod", "dropbox-prod"],
    "gdpr_request": ["gmail-prod", "slack-prod", "github-prod"],
    "ip_filing": ["gmail-prod", "dropbox-prod", "slack-prod"],
    "maintenance_request": ["stripe-prod", "slack-prod", "gmail-prod"],
    "tenant_screening": ["gmail-prod", "slack-prod", "salesforce-prod"],
    "content_moderation": ["slack-prod", "gmail-prod"],
    "licensing": ["stripe-prod", "gmail-prod", "slack-prod"],
    "environmental_incident": ["gmail-prod", "slack-prod"],
    "renewable_energy": ["stripe-prod", "gmail-prod", "slack-prod"],
}

# Agent → required approver roles
AGENT_APPROVERS = {
    "ecommerce": ["sales_manager", "cfo", "cs_agent", "cs_manager", "team_lead"],
    "hr": ["hr_manager", "ceo", "it_manager"],
    "devops": ["maintainer", "lead_engineer", "cto"],
    "opensource": ["maintainer", "lead_maintainer", "cto", "treasurer"],
    "research": ["pi", "finance", "hr_manager", "cto"],
    "fintech": ["manager", "operations", "finance", "cfo", "procurement", "legal"],
    # ── New agents ──
    "invoice": ["cfo", "legal"],
    "expense": ["manager", "cfo"],
    "subscription": ["ceo", "cfo", "manager"],
    "vendor_payment": ["finance", "cfo", "ceo", "procurement"],
    "churn_prevention": ["manager", "ceo", "cfo"],
    "carbon_credit": ["sustainability_officer", "cfo"],
    "release_manager": ["maintainer", "oncall_engineer", "lead_engineer"],
    "security_incident": ["security_lead", "cto"],
    "dependency_update": ["lead_engineer", "maintainer", "cto"],
    "db_migration": ["dba", "cto"],
    "api_key_rotation": ["security_lead", "cto"],
    "compliance_audit": ["compliance_officer", "legal", "ceo"],
    "recruitment": ["hr_manager", "cfo", "ceo"],
    "access_provisioning": ["it_manager", "cto", "cfo"],
    "leave_management": ["manager", "hr_manager", "ceo"],
    "contractor_onboarding": ["legal", "ceo", "manager"],
    "performance_review": ["hr_manager", "manager", "cfo"],
    "support_escalation": ["cs_manager", "cfo", "legal"],
    "account_takeover": ["security_lead", "legal"],
    "sla_breach": ["cs_manager", "cfo", "legal"],
    "patient_data": ["doctor", "patient_rep"],
    "medical_supply": ["chief_doctor", "cfo"],
    "prescription_refill": ["doctor", "pharmacist"],
    "research_data": ["ethics_board", "chief_doctor"],
    "grade_override": ["teacher", "department_head"],
    "scholarship": ["scholarship_committee", "rector"],
    "research_grant": ["department_head", "rector", "external_board"],
    "contract_signing": ["legal", "ceo"],
    "gdpr_request": ["privacy_officer", "cto"],
    "ip_filing": ["legal", "ceo"],
    "maintenance_request": ["building_manager", "property_owner"],
    "tenant_screening": ["property_manager", "legal"],
    "content_moderation": ["moderator", "senior_moderator", "legal"],
    "licensing": ["legal", "ceo"],
    "environmental_incident": ["ceo", "environmental_officer"],
    "renewable_energy": ["cfo", "ceo"],
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

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
        "category": "finance",
        "categoryLabel": "Commerce & Finance",
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
        "category": "hr",
        "categoryLabel": "Human Resources",
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
        "category": "devops",
        "categoryLabel": "DevOps & Software",
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
        "category": "devops",
        "categoryLabel": "DevOps & Software",
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
        "category": "education",
        "categoryLabel": "Education",
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
        "category": "finance",
        "categoryLabel": "Commerce & Finance",
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
        "category": "media",
        "categoryLabel": "Media & Content",
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

    # ═══════════════════════════════════════════════════════════════════════════
    # NEW DEMO AGENTS (30 agents across 10 categories)
    # ═══════════════════════════════════════════════════════════════════════════

    # ── Invoice Agent ────────────────────────────────────────────────────────
    {
        "id": "invoice",
        "title": "Invoice Agent",
        "icon": "FileText",
        "category": "finance",
        "categoryLabel": "Commerce & Finance",
        "description": "Automated invoicing and collections. Invoices under $1,000 send automatically, overdue reminders are instant, legal collections require CFO + Legal step-up.",
        "setupInfo": [
            {"type": "connection", "name": "stripe-prod", "detail": "Payment processing"},
            {"type": "connection", "name": "gmail-prod", "detail": "Invoice and reminder emails"},
            {"type": "approver", "name": "CFO", "detail": "Approves invoices $1k-$5k"},
            {"type": "approver", "name": "Legal", "detail": "Co-approves legal collections"},
            {"type": "rule", "name": "Invoice medium ($1k-$5k)", "detail": "any_one -> CFO"},
            {"type": "rule", "name": "Invoice large ($5k+)", "detail": "all_of_n -> CFO + Legal"},
            {"type": "rule", "name": "Legal collection", "detail": "all_of_n -> CFO + Legal"},
        ],
        "scenarios": [
            {
                "title": "Small invoice ($800)",
                "description": "Under $1,000 threshold - sends automatically without approval.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"amount_usd": 800, "customer": "client@acme.com", "description": "Consulting Q1", "type": "invoice"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Invoice Agent", "sub": "send_invoice($800)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Stripe + Gmail", "sub": "Invoice sent to client"},
                ],
            },
            {
                "title": "Medium invoice ($3,500)",
                "description": "CFO reviews and approves invoices between $1,000-$5,000.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"amount_usd": 3500, "customer": "partner@bigcorp.com", "description": "Integration project", "type": "invoice"},
                "badge": "info", "badgeLabel": "any_one",
                "flow": [
                    {"type": "agent", "label": "Invoice Agent", "sub": "send_invoice($3,500)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: medium invoice"},
                    {"type": "approver", "label": "CFO", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe + Gmail", "sub": "Invoice sent"},
                ],
            },
            {
                "title": "Legal collection",
                "description": "Initiating legal proceedings requires both CFO and Legal approval.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "legal_collection", "customer": "delinquent@example.com", "amount_usd": 15000, "subject": "Final Notice: INV-2024-089"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Invoice Agent", "sub": "legal_collection(...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: legal collection"},
                    {"type": "approver", "label": "CFO", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "Legal", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Gmail", "sub": "Legal notice sent"},
                ],
            },
        ],
    },

    # ── Expense Agent ────────────────────────────────────────────────────────
    {
        "id": "expense",
        "title": "Expense Approval Agent",
        "icon": "Briefcase",
        "category": "finance",
        "categoryLabel": "Commerce & Finance",
        "description": "Employee expense requests with tiered approvals. Office supplies auto-approve, equipment needs manager sign-off, large expenses require CFO step-up with partial approval.",
        "setupInfo": [
            {"type": "connection", "name": "stripe-prod", "detail": "Expense reimbursement"},
            {"type": "approver", "name": "Manager", "detail": "Approves $500-$5,000"},
            {"type": "approver", "name": "CFO", "detail": "Co-approves $5,000+"},
            {"type": "rule", "name": "Expense medium", "detail": "any_one -> Manager"},
            {"type": "rule", "name": "Expense large", "detail": "all_of_n -> Manager + CFO"},
        ],
        "scenarios": [
            {
                "title": "Office supplies ($45)",
                "description": "Small office supply purchases auto-approve instantly.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"amount_usd": 45, "category": "office_supplies", "description": "Printer paper and pens", "type": "expense"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Expense Agent", "sub": "submit_expense($45)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Stripe", "sub": "Reimbursed $45"},
                ],
            },
            {
                "title": "New laptop ($2,500)",
                "description": "Equipment purchases need manager approval.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"amount_usd": 2500, "category": "equipment", "description": "MacBook Pro 16-inch", "type": "expense"},
                "badge": "info", "badgeLabel": "any_one",
                "flow": [
                    {"type": "agent", "label": "Expense Agent", "sub": "submit_expense($2,500)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: medium expense"},
                    {"type": "approver", "label": "Manager", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "Reimbursed $2,500"},
                ],
            },
            {
                "title": "Team offsite ($8,000)",
                "description": "Large expenses require both Manager and CFO to approve.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"amount_usd": 8000, "category": "team_event", "description": "Q2 team offsite Lisbon", "type": "expense"},
                "badge": "warning", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Expense Agent", "sub": "submit_expense($8,000)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: large expense"},
                    {"type": "approver", "label": "Manager", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "CFO", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "Reimbursed $8,000"},
                ],
            },
        ],
    },

    # ── Subscription Manager ─────────────────────────────────────────────────
    {
        "id": "subscription",
        "title": "Subscription Manager",
        "icon": "Zap",
        "category": "finance",
        "categoryLabel": "Commerce & Finance",
        "description": "Subscription lifecycle management. Free-to-paid upgrades are automatic, enterprise pricing needs CEO approval, bulk cancellations require CFO step-up.",
        "setupInfo": [
            {"type": "connection", "name": "stripe-prod", "detail": "Subscription billing"},
            {"type": "approver", "name": "CEO", "detail": "Approves enterprise pricing"},
            {"type": "approver", "name": "CFO", "detail": "Co-approves bulk cancellations"},
            {"type": "rule", "name": "Enterprise pricing", "detail": "specific -> CEO"},
            {"type": "rule", "name": "Bulk cancellation", "detail": "all_of_n -> CFO + Manager"},
        ],
        "scenarios": [
            {
                "title": "Upgrade free to pro ($29/mo)",
                "description": "Standard plan upgrades process automatically.",
                "connection": "stripe-prod", "action": "subscription",
                "params": {"type": "upgrade", "customer": "user@example.com", "plan": "pro", "amount_usd": 29},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Sub Manager", "sub": "upgrade(free -> pro)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Stripe", "sub": "Subscription upgraded"},
                ],
            },
            {
                "title": "Enterprise pricing ($5,000/mo)",
                "description": "Custom enterprise plans require CEO sign-off.",
                "connection": "stripe-prod", "action": "subscription",
                "params": {"type": "enterprise_pricing", "customer": "bigcorp@example.com", "amount_usd": 5000},
                "badge": "warning", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "Sub Manager", "sub": "enterprise_pricing(...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: enterprise"},
                    {"type": "approver", "label": "CEO", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "Enterprise plan created"},
                ],
            },
            {
                "title": "Bulk cancel (50 accounts)",
                "description": "Mass cancellations need CFO and Manager approval to prevent revenue loss.",
                "connection": "stripe-prod", "action": "subscription",
                "params": {"type": "bulk_cancel", "count": 50, "reason": "Product sunset"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Sub Manager", "sub": "bulk_cancel(50)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: bulk cancel"},
                    {"type": "approver", "label": "CFO", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "Manager", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "50 subscriptions cancelled"},
                ],
            },
        ],
    },

    # ── Vendor Payment Agent ─────────────────────────────────────────────────
    {
        "id": "vendor_payment",
        "title": "Vendor Payment Agent",
        "icon": "CreditCard",
        "category": "finance",
        "categoryLabel": "Commerce & Finance",
        "description": "Supplier payment automation. Small payments auto-approve, medium need Finance, large need CFO + CEO. First-time vendor payments require extra Procurement + Legal vetting.",
        "setupInfo": [
            {"type": "connection", "name": "stripe-prod", "detail": "Vendor payments"},
            {"type": "approver", "name": "Finance", "detail": "Approves $1k-$10k"},
            {"type": "approver", "name": "CFO", "detail": "Co-approves $10k+"},
            {"type": "approver", "name": "CEO", "detail": "Co-approves $10k+"},
            {"type": "rule", "name": "Vendor medium ($1k-$10k)", "detail": "any_one -> Finance"},
            {"type": "rule", "name": "Vendor large ($10k+)", "detail": "all_of_n -> CFO + CEO"},
            {"type": "rule", "name": "New vendor payment", "detail": "all_of_n -> Procurement + Legal"},
        ],
        "scenarios": [
            {
                "title": "Small vendor payment ($800)",
                "description": "Routine payments under $1,000 process automatically.",
                "connection": "stripe-prod", "action": "vendor_payment",
                "params": {"amount_usd": 800, "vendor_name": "CloudHost", "invoice_id": "INV-CH-042", "is_new_vendor": False},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Vendor Agent", "sub": "pay($800, CloudHost)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Stripe", "sub": "$800 -> CloudHost"},
                ],
            },
            {
                "title": "New vendor first payment ($15,000)",
                "description": "First payment to an unverified vendor requires Procurement + Legal vetting.",
                "connection": "stripe-prod", "action": "vendor_payment",
                "params": {"amount_usd": 15000, "vendor_name": "NewTech GmbH", "invoice_id": "INV-NT-001", "is_new_vendor": True},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Vendor Agent", "sub": "pay($15k, NewTech, new=True)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: new vendor"},
                    {"type": "approver", "label": "Procurement", "sub": "Vendor vetting -> Approve"},
                    {"type": "approver", "label": "Legal", "sub": "Contract review -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "$15,000 -> NewTech GmbH"},
                ],
            },
        ],
    },

    # ── Churn Prevention Agent ───────────────────────────────────────────────
    {
        "id": "churn_prevention",
        "title": "Churn Prevention Agent",
        "icon": "Shield",
        "category": "finance",
        "categoryLabel": "Commerce & Finance",
        "description": "Customer retention automation. 10% discounts are instant, 30% needs manager approval, custom enterprise packages require CEO + CFO sequential sign-off.",
        "setupInfo": [
            {"type": "connection", "name": "stripe-prod", "detail": "Credits and discounts"},
            {"type": "approver", "name": "Manager", "detail": "Approves 11-30% discounts"},
            {"type": "approver", "name": "CEO", "detail": "Approves custom packages"},
            {"type": "approver", "name": "CFO", "detail": "Co-approves enterprise custom"},
            {"type": "rule", "name": "Retention discount medium", "detail": "any_one -> Manager"},
            {"type": "rule", "name": "Custom package", "detail": "specific -> CEO"},
        ],
        "scenarios": [
            {
                "title": "10% retention discount",
                "description": "Small retention discounts auto-apply without approval.",
                "connection": "stripe-prod", "action": "credit",
                "params": {"discount_pct": 10, "customer": "leaving@example.com", "reason": "Price sensitivity"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Churn Agent", "sub": "offer_discount(10%)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Stripe", "sub": "10% credit applied"},
                ],
            },
            {
                "title": "25% enterprise discount",
                "description": "Significant discounts need manager approval.",
                "connection": "stripe-prod", "action": "credit",
                "params": {"discount_pct": 25, "customer": "enterprise@bigcorp.com", "reason": "Competitor offer"},
                "badge": "info", "badgeLabel": "any_one",
                "flow": [
                    {"type": "agent", "label": "Churn Agent", "sub": "offer_discount(25%)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: medium discount"},
                    {"type": "approver", "label": "Manager", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "25% credit applied"},
                ],
            },
            {
                "title": "Custom package for VIP",
                "description": "Bespoke retention package requires CEO approval.",
                "connection": "stripe-prod", "action": "credit",
                "params": {"type": "custom_package", "customer": "vip@enterprise.com", "description": "Custom SLA + dedicated support"},
                "badge": "warning", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "Churn Agent", "sub": "custom_package(...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: custom package"},
                    {"type": "approver", "label": "CEO", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "Custom package created"},
                ],
            },
        ],
    },

    # ── Carbon Credit Agent ──────────────────────────────────────────────────
    {
        "id": "carbon_credit",
        "title": "Carbon Credit Agent",
        "icon": "TreePine",
        "category": "finance",
        "categoryLabel": "Commerce & Finance",
        "description": "Carbon credit trading. Small lots auto-purchase, large lots need Sustainability Officer, forward contracts require CFO + Sustainability step-up.",
        "setupInfo": [
            {"type": "connection", "name": "stripe-prod", "detail": "Credit purchases"},
            {"type": "approver", "name": "Sustainability Officer", "detail": "Approves large lots"},
            {"type": "approver", "name": "CFO", "detail": "Co-approves forward contracts"},
            {"type": "rule", "name": "Carbon large ($10k-$50k)", "detail": "any_one -> Sustainability"},
            {"type": "rule", "name": "Carbon forward contract", "detail": "all_of_n -> CFO + Sustainability"},
        ],
        "scenarios": [
            {
                "title": "Small purchase ($5,000)",
                "description": "Under $10,000 - processes automatically.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"type": "carbon_credit", "amount_usd": 5000, "quantity": 100, "price_per_ton": 50},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Carbon Agent", "sub": "purchase(100 tons, $5k)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Stripe", "sub": "100 credits purchased"},
                ],
            },
            {
                "title": "Large lot ($22,500)",
                "description": "Sustainability Officer reviews large carbon credit purchases.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"type": "carbon_credit", "amount_usd": 22500, "quantity": 500, "price_per_ton": 45},
                "badge": "info", "badgeLabel": "any_one",
                "flow": [
                    {"type": "agent", "label": "Carbon Agent", "sub": "purchase(500 tons, $22.5k)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: large carbon purchase"},
                    {"type": "approver", "label": "Sustainability Officer", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "500 credits purchased"},
                ],
            },
            {
                "title": "3-year forward contract",
                "description": "Long-term agreements need CFO + Sustainability Officer.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"type": "carbon_forward", "amount_usd": 150000, "years": 3, "annual_tons": 1000},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Carbon Agent", "sub": "forward_contract(3yr)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: forward contract"},
                    {"type": "approver", "label": "CFO", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "Sustainability Officer", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "Contract signed ($150k)"},
                ],
            },
        ],
    },

    # ── Release Manager Agent ────────────────────────────────────────────────
    {
        "id": "release_manager",
        "title": "Release Manager Agent",
        "icon": "Server",
        "category": "devops",
        "categoryLabel": "DevOps & Software",
        "description": "Deployment pipeline management. Staging auto-deploys, production needs maintainer approval, hotfixes page on-call, rollbacks have 2-minute timeout.",
        "setupInfo": [
            {"type": "connection", "name": "github-main", "detail": "Deploy and rollback"},
            {"type": "approver", "name": "Maintainer", "detail": "Approves production deploys"},
            {"type": "approver", "name": "On-Call Engineer", "detail": "Approves hotfixes"},
            {"type": "rule", "name": "Production deploy", "detail": "any_one -> Maintainer"},
            {"type": "rule", "name": "Hotfix deploy", "detail": "specific -> On-Call (120s)"},
        ],
        "scenarios": [
            {
                "title": "Deploy to staging",
                "description": "Staging deployments run automatically - no gate needed.",
                "connection": "github-main", "action": "deploy",
                "params": {"ref": "main", "environment": "staging", "service": "api"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Release Mgr", "sub": "deploy(staging)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "GitHub Actions", "sub": "Deploy -> staging"},
                ],
            },
            {
                "title": "Deploy to production (v2.5.0)",
                "description": "Production deploys require maintainer approval.",
                "connection": "github-main", "action": "deploy",
                "params": {"ref": "v2.5.0", "environment": "production", "service": "api"},
                "badge": "info", "badgeLabel": "any_one",
                "flow": [
                    {"type": "agent", "label": "Release Mgr", "sub": "deploy(production, v2.5.0)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: production deploy"},
                    {"type": "approver", "label": "Maintainer", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "GitHub Actions", "sub": "Deploy v2.5.0 -> production"},
                ],
            },
            {
                "title": "Production rollback (v2.4.8)",
                "description": "Emergency rollback with 2-minute timeout.",
                "connection": "github-main", "action": "rollback",
                "params": {"env": "production", "version": "v2.4.8", "reason": "P0 latency spike"},
                "badge": "warning", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "Release Mgr", "sub": "rollback(v2.4.8)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: rollback (120s timeout)"},
                    {"type": "approver", "label": "Lead Engineer", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "GitHub Actions", "sub": "Rollback -> v2.4.8"},
                ],
            },
        ],
    },

    # ── Security Incident Agent ──────────────────────────────────────────────
    {
        "id": "security_incident",
        "title": "Security Incident Agent",
        "icon": "AlertTriangle",
        "category": "devops",
        "categoryLabel": "DevOps & Software",
        "description": "Security breach response. Alerts auto-log, repo locking needs Security Lead, revoking production access requires CTO + Security Lead all_of_n.",
        "setupInfo": [
            {"type": "connection", "name": "github-prod", "detail": "Repo lock and token revocation"},
            {"type": "approver", "name": "Security Lead", "detail": "Approves repo locks"},
            {"type": "approver", "name": "CTO", "detail": "Co-approves access revocation"},
            {"type": "rule", "name": "Lock repository", "detail": "specific -> Security Lead"},
            {"type": "rule", "name": "Revoke access", "detail": "all_of_n -> CTO + Security Lead"},
        ],
        "scenarios": [
            {
                "title": "Log security alert",
                "description": "Alert logging is automatic - no approval needed.",
                "connection": "slack-prod", "action": "send_message",
                "params": {"channel": "#security", "message": "Suspicious login from IP 45.33.32.156"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Security Agent", "sub": "log_alert(...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Slack", "sub": "Alert logged to #security"},
                ],
            },
            {
                "title": "Lock repository",
                "description": "Repository lockdown requires Security Lead approval.",
                "connection": "github-prod", "action": "lock_repo",
                "params": {"repo": "acme/api", "reason": "Suspected compromise"},
                "badge": "warning", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "Security Agent", "sub": "lock_repo(acme/api)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: lock repo"},
                    {"type": "approver", "label": "Security Lead", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "GitHub", "sub": "Repository locked"},
                ],
            },
            {
                "title": "Revoke all production tokens",
                "description": "Nuclear option - CTO and Security Lead must both approve.",
                "connection": "github-prod", "action": "revoke_tokens",
                "params": {"scope": "production", "reason": "Confirmed breach"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Security Agent", "sub": "revoke_all_tokens()"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: revoke tokens"},
                    {"type": "approver", "label": "CTO", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "Security Lead", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "GitHub", "sub": "All tokens revoked"},
                ],
            },
        ],
    },

    # ── Dependency Update Agent ──────────────────────────────────────────────
    {
        "id": "dependency_update",
        "title": "Dependency Update Agent",
        "icon": "Package",
        "category": "devops",
        "categoryLabel": "DevOps & Software",
        "description": "Package update management. Patches auto-merge, minor updates need Lead Engineer, major breaking changes require full team approval.",
        "setupInfo": [
            {"type": "connection", "name": "github-prod", "detail": "PR merges"},
            {"type": "approver", "name": "Lead Engineer", "detail": "Approves minor updates"},
            {"type": "approver", "name": "CTO", "detail": "Co-approves major updates"},
            {"type": "rule", "name": "Minor update", "detail": "any_one -> Lead Engineer"},
            {"type": "rule", "name": "Major update", "detail": "all_of_n -> Lead + Maintainer + CTO"},
        ],
        "scenarios": [
            {
                "title": "Patch: lodash 4.17.20 -> 4.17.21",
                "description": "Patch updates auto-merge without review.",
                "connection": "github-prod", "action": "merge_pr",
                "params": {"package": "lodash", "from_version": "4.17.20", "to_version": "4.17.21", "update_type": "patch"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Dep Agent", "sub": "update(lodash, patch)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "GitHub", "sub": "PR merged"},
                ],
            },
            {
                "title": "Minor: react 18.2 -> 18.3",
                "description": "Minor updates need Lead Engineer review.",
                "connection": "github-prod", "action": "merge_pr",
                "params": {"package": "react", "from_version": "18.2.0", "to_version": "18.3.0", "update_type": "minor"},
                "badge": "info", "badgeLabel": "any_one",
                "flow": [
                    {"type": "agent", "label": "Dep Agent", "sub": "update(react, minor)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: minor update"},
                    {"type": "approver", "label": "Lead Engineer", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "GitHub", "sub": "PR merged"},
                ],
            },
            {
                "title": "Major: webpack 5.x -> 6.0 (BREAKING)",
                "description": "Breaking changes need all team leads to approve.",
                "connection": "github-prod", "action": "merge_pr",
                "params": {"package": "webpack", "from_version": "5.91.0", "to_version": "6.0.0", "update_type": "major"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Dep Agent", "sub": "update(webpack, MAJOR)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: major update"},
                    {"type": "approver", "label": "Lead Engineer", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "Maintainer", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "CTO", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "GitHub", "sub": "PR merged"},
                ],
            },
        ],
    },

    # ── Database Migration Agent ─────────────────────────────────────────────
    {
        "id": "db_migration",
        "title": "Database Migration Agent",
        "icon": "Database",
        "category": "devops",
        "categoryLabel": "DevOps & Software",
        "description": "Schema change management. Dev auto-runs, staging needs DBA, production requires DBA + CTO step-up. Blackout window blocks night migrations.",
        "setupInfo": [
            {"type": "connection", "name": "github-prod", "detail": "Migration deployments"},
            {"type": "approver", "name": "DBA", "detail": "Approves staging + production"},
            {"type": "approver", "name": "CTO", "detail": "Co-approves production"},
            {"type": "rule", "name": "Staging migration", "detail": "any_one -> DBA"},
            {"type": "rule", "name": "Production migration", "detail": "all_of_n -> DBA + CTO"},
        ],
        "scenarios": [
            {
                "title": "Dev: add index on users.email",
                "description": "Dev migrations run automatically.",
                "connection": "github-prod", "action": "deploy",
                "params": {"type": "migration", "env": "dev", "migration_name": "add_users_email_index"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Migration Agent", "sub": "migrate(dev)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Database", "sub": "Index created"},
                ],
            },
            {
                "title": "Staging: alter table orders",
                "description": "Staging migrations need DBA review.",
                "connection": "github-prod", "action": "deploy",
                "params": {"type": "migration", "env": "staging", "migration_name": "alter_orders_add_status"},
                "badge": "info", "badgeLabel": "any_one",
                "flow": [
                    {"type": "agent", "label": "Migration Agent", "sub": "migrate(staging)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: staging migration"},
                    {"type": "approver", "label": "DBA", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Database", "sub": "Table altered"},
                ],
            },
            {
                "title": "Production: drop column (destructive)",
                "description": "Destructive production changes need DBA + CTO.",
                "connection": "github-prod", "action": "deploy",
                "params": {"type": "migration", "env": "production", "migration_name": "drop_legacy_column", "description": "Remove deprecated user.old_email"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Migration Agent", "sub": "migrate(production, DROP)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: production migration"},
                    {"type": "approver", "label": "DBA", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "CTO", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Database", "sub": "Column dropped"},
                ],
            },
        ],
    },

    # ── API Key Rotation Agent ───────────────────────────────────────────────
    {
        "id": "api_key_rotation",
        "title": "API Key Rotation Agent",
        "icon": "Key",
        "category": "devops",
        "categoryLabel": "DevOps & Software",
        "description": "Credential rotation automation. Scheduled rotations auto-execute, emergency rotations need Security Lead, third-party keys require CTO step-up.",
        "setupInfo": [
            {"type": "connection", "name": "github-prod", "detail": "Key deployments"},
            {"type": "approver", "name": "Security Lead", "detail": "Emergency rotations"},
            {"type": "approver", "name": "CTO", "detail": "Third-party key changes"},
            {"type": "rule", "name": "Emergency rotation", "detail": "specific -> Security Lead"},
            {"type": "rule", "name": "Third-party rotation", "detail": "all_of_n -> Security + CTO"},
        ],
        "scenarios": [
            {
                "title": "Scheduled Stripe key rotation",
                "description": "Planned rotations execute automatically.",
                "connection": "github-prod", "action": "deploy",
                "params": {"type": "key_rotation", "service": "stripe", "urgency": "scheduled"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Key Agent", "sub": "rotate(stripe, scheduled)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Vault", "sub": "Key rotated + deployed"},
                ],
            },
            {
                "title": "Emergency AWS key rotation",
                "description": "Compromised credentials need Security Lead sign-off.",
                "connection": "github-prod", "action": "deploy",
                "params": {"type": "key_rotation", "service": "aws", "urgency": "emergency", "reason": "Key exposed in logs"},
                "badge": "warning", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "Key Agent", "sub": "rotate(aws, EMERGENCY)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: emergency rotation"},
                    {"type": "approver", "label": "Security Lead", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Vault", "sub": "AWS key rotated"},
                ],
            },
            {
                "title": "Third-party partner key",
                "description": "External partner keys require CTO + Security Lead.",
                "connection": "github-prod", "action": "deploy",
                "params": {"type": "key_rotation", "service": "partner-api", "scope": "third_party", "provider": "PaymentCo"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Key Agent", "sub": "rotate(partner, 3rd-party)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: third-party key"},
                    {"type": "approver", "label": "Security Lead", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "CTO", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Vault", "sub": "Partner key rotated"},
                ],
            },
        ],
    },

    # ── Compliance Audit Agent ───────────────────────────────────────────────
    {
        "id": "compliance_audit",
        "title": "Compliance Audit Agent",
        "icon": "FileCheck",
        "category": "devops",
        "categoryLabel": "DevOps & Software",
        "description": "Regulatory compliance tracking. Routine checks auto-run, violations notify Compliance Officer, regulatory filings need Legal + CEO step-up.",
        "setupInfo": [
            {"type": "connection", "name": "gmail-prod", "detail": "Compliance reports"},
            {"type": "approver", "name": "Compliance Officer", "detail": "Reviews violations"},
            {"type": "approver", "name": "Legal", "detail": "Co-approves filings"},
            {"type": "rule", "name": "Violation report", "detail": "specific -> Compliance Officer"},
            {"type": "rule", "name": "Regulatory filing", "detail": "all_of_n -> Legal + CEO"},
        ],
        "scenarios": [
            {
                "title": "Routine SOC2 check",
                "description": "Automated compliance scans run without approval.",
                "connection": "slack-prod", "action": "send_message",
                "params": {"channel": "#compliance", "message": "SOC2 audit pass: all 42 controls green"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Compliance Agent", "sub": "routine_check(SOC2)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Slack", "sub": "Report posted"},
                ],
            },
            {
                "title": "GDPR violation detected",
                "description": "Compliance Officer reviews and determines severity.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "violation_report", "framework": "GDPR", "description": "PII found in logs", "severity": "medium"},
                "badge": "warning", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "Compliance Agent", "sub": "report_violation(GDPR)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: violation report"},
                    {"type": "approver", "label": "Compliance Officer", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Gmail", "sub": "Report filed"},
                ],
            },
            {
                "title": "File report to regulator",
                "description": "Official regulatory filings need Legal + CEO.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "regulatory_filing", "authority": "DPA Ireland", "subject": "Mandatory breach notification"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Compliance Agent", "sub": "file_regulatory(DPA)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: regulatory filing"},
                    {"type": "approver", "label": "Legal", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "CEO", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Gmail", "sub": "Report filed with DPA"},
                ],
            },
        ],
    },

    # ── Recruitment Agent ────────────────────────────────────────────────────
    {
        "id": "recruitment",
        "title": "Recruitment Agent",
        "icon": "UserPlus",
        "category": "hr",
        "categoryLabel": "Human Resources",
        "description": "Full hiring lifecycle. Interview invites auto-send, offer letters need HR, salary packages require HR + CFO sequential, terminations need HR + CEO all_of_n.",
        "setupInfo": [
            {"type": "connection", "name": "gmail-prod", "detail": "HR emails"},
            {"type": "approver", "name": "HR Manager", "detail": "Reviews offers and packages"},
            {"type": "approver", "name": "CFO", "detail": "Co-approves salary packages"},
            {"type": "rule", "name": "Offer letter", "detail": "specific -> HR Manager"},
            {"type": "rule", "name": "Salary package", "detail": "all_of_n -> HR + CFO"},
        ],
        "scenarios": [
            {
                "title": "Interview invite",
                "description": "Standard interview invites send automatically.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "invite", "recipient": "candidate@example.com", "subject": "Interview: Senior Engineer"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Recruitment", "sub": "send_invite(...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Gmail", "sub": "Invite sent"},
                ],
            },
            {
                "title": "Offer letter ($180k)",
                "description": "HR Manager reviews salary and terms.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "offer_letter", "recipient": "hire@example.com", "subject": "Offer: Senior Engineer $180k"},
                "badge": "info", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "Recruitment", "sub": "send_offer(...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: offer letter"},
                    {"type": "approver", "label": "HR Manager", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Gmail", "sub": "Offer sent"},
                ],
            },
            {
                "title": "Salary package ($220k + equity)",
                "description": "Competitive packages need both HR and CFO sign-off.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "salary_package", "candidate": "senior@example.com", "salary": 220000, "equity": "0.5%"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Recruitment", "sub": "salary_package($220k + equity)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: salary package"},
                    {"type": "approver", "label": "HR Manager", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "CFO", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Gmail", "sub": "Package sent"},
                ],
            },
        ],
    },

    # ── Access Provisioning Agent ────────────────────────────────────────────
    {
        "id": "access_provisioning",
        "title": "Access Provisioning Agent",
        "icon": "DoorOpen",
        "category": "hr",
        "categoryLabel": "Human Resources",
        "description": "System access management. Standard access needs IT, admin needs CTO, financial systems need CFO + CTO. Departing employee revocation is automatic.",
        "setupInfo": [
            {"type": "connection", "name": "github-prod", "detail": "Access management"},
            {"type": "approver", "name": "IT Manager", "detail": "Standard access"},
            {"type": "approver", "name": "CTO", "detail": "Admin access"},
            {"type": "rule", "name": "Standard access", "detail": "any_one -> IT Manager"},
            {"type": "rule", "name": "Admin access", "detail": "specific -> CTO"},
            {"type": "rule", "name": "Financial access", "detail": "all_of_n -> CFO + CTO"},
        ],
        "scenarios": [
            {
                "title": "Revoke departed employee",
                "description": "Immediate revocation - no approval delay.",
                "connection": "github-prod", "action": "remove_member",
                "params": {"username": "departed", "org": "acme-corp", "reason": "Employment ended"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Access Agent", "sub": "revoke(departed)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "GitHub", "sub": "Access revoked"},
                ],
            },
            {
                "title": "Grant admin access",
                "description": "Admin privileges require CTO approval.",
                "connection": "github-prod", "action": "add_member",
                "params": {"username": "senior-dev", "role": "admin", "access_level": "admin"},
                "badge": "warning", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "Access Agent", "sub": "grant(admin)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: admin access"},
                    {"type": "approver", "label": "CTO", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "GitHub", "sub": "Admin access granted"},
                ],
            },
            {
                "title": "Grant financial system access",
                "description": "Finance systems need both CFO and CTO.",
                "connection": "github-prod", "action": "add_member",
                "params": {"username": "finance-lead", "access_level": "financial"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Access Agent", "sub": "grant(financial)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: financial access"},
                    {"type": "approver", "label": "CFO", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "CTO", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Systems", "sub": "Financial access granted"},
                ],
            },
        ],
    },

    # ── Leave Management Agent ───────────────────────────────────────────────
    {
        "id": "leave_management",
        "title": "Leave Management Agent",
        "icon": "Clock",
        "category": "hr",
        "categoryLabel": "Human Resources",
        "description": "Leave request management. 1-2 day requests auto-approve, weekly leave needs manager, long sabbaticals need HR, critical period leave requires CEO step-up.",
        "setupInfo": [
            {"type": "connection", "name": "calendar-prod", "detail": "Calendar blocking"},
            {"type": "approver", "name": "Manager", "detail": "Weekly leave"},
            {"type": "approver", "name": "HR Manager", "detail": "Long leave"},
            {"type": "rule", "name": "Week leave (3-5d)", "detail": "any_one -> Manager"},
            {"type": "rule", "name": "Critical period", "detail": "all_of_n -> Manager + CEO"},
        ],
        "scenarios": [
            {
                "title": "1 day off (Friday)",
                "description": "Short leaves auto-approve instantly.",
                "connection": "calendar-prod", "action": "block_time",
                "params": {"employee": "alice@company.com", "days": 1, "start_date": "2026-04-03"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Leave Agent", "sub": "request(1 day)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Calendar", "sub": "Day blocked"},
                ],
            },
            {
                "title": "1 week vacation",
                "description": "Weekly leave needs manager sign-off.",
                "connection": "calendar-prod", "action": "block_time",
                "params": {"employee": "bob@company.com", "days": 5, "start_date": "2026-04-15"},
                "badge": "info", "badgeLabel": "any_one",
                "flow": [
                    {"type": "agent", "label": "Leave Agent", "sub": "request(5 days)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: week leave"},
                    {"type": "approver", "label": "Manager", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Calendar", "sub": "Week blocked"},
                ],
            },
            {
                "title": "Leave during product launch",
                "description": "Critical period leave needs Manager + CEO.",
                "connection": "calendar-prod", "action": "block_time",
                "params": {"employee": "lead@company.com", "days": 3, "is_critical_period": True, "reason": "Family emergency"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Leave Agent", "sub": "request(critical period)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: critical period"},
                    {"type": "approver", "label": "Manager", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "CEO", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Calendar", "sub": "Leave approved"},
                ],
            },
        ],
    },

    # ── Contractor Onboarding Agent ──────────────────────────────────────────
    {
        "id": "contractor_onboarding",
        "title": "Contractor Onboarding Agent",
        "icon": "UserCheck",
        "category": "hr",
        "categoryLabel": "Human Resources",
        "description": "Freelancer onboarding automation. NDA sending is automatic, payment agreements need Legal, contracts over $10k require CEO step-up.",
        "setupInfo": [
            {"type": "connection", "name": "gmail-prod", "detail": "Contract emails"},
            {"type": "connection", "name": "stripe-prod", "detail": "Payment setup"},
            {"type": "approver", "name": "Legal", "detail": "Reviews agreements"},
            {"type": "approver", "name": "CEO", "detail": "Large contracts"},
            {"type": "rule", "name": "Payment agreement", "detail": "specific -> Legal"},
            {"type": "rule", "name": "Large contract ($10k+)", "detail": "all_of_n -> Legal + CEO"},
        ],
        "scenarios": [
            {
                "title": "Send NDA",
                "description": "Standard NDAs send automatically.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "nda", "recipient": "contractor@freelance.com", "subject": "NDA for Project Alpha"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Onboarding", "sub": "send_nda(...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Gmail", "sub": "NDA sent"},
                ],
            },
            {
                "title": "Payment agreement ($5k/mo)",
                "description": "Legal reviews payment terms and rates.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"type": "contractor_agreement", "contractor": "dev@freelance.com", "amount_usd": 5000},
                "badge": "info", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "Onboarding", "sub": "setup_payment($5k)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: payment agreement"},
                    {"type": "approver", "label": "Legal", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "Agreement created"},
                ],
            },
            {
                "title": "Large contract ($15k/mo)",
                "description": "High-value contracts need Legal + CEO.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"type": "contractor_agreement", "contractor": "agency@consulting.com", "amount_usd": 15000},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Onboarding", "sub": "setup_contract($15k)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: large contract"},
                    {"type": "approver", "label": "Legal", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "CEO", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "Contract signed"},
                ],
            },
        ],
    },

    # ── Performance Review Agent ─────────────────────────────────────────────
    {
        "id": "performance_review",
        "title": "Performance Review Agent",
        "icon": "ClipboardList",
        "category": "hr",
        "categoryLabel": "Human Resources",
        "description": "Performance and promotion management. Review forms auto-send, promotions need HR + Manager, salary increases require HR + CFO sequential approval.",
        "setupInfo": [
            {"type": "connection", "name": "gmail-prod", "detail": "Review communications"},
            {"type": "approver", "name": "HR Manager", "detail": "All personnel actions"},
            {"type": "approver", "name": "Manager", "detail": "Co-approves promotions"},
            {"type": "approver", "name": "CFO", "detail": "Co-approves salary changes"},
            {"type": "rule", "name": "Promotion", "detail": "all_of_n -> HR + Manager"},
            {"type": "rule", "name": "Salary increase", "detail": "all_of_n -> HR + CFO"},
        ],
        "scenarios": [
            {
                "title": "Send quarterly review form",
                "description": "Review forms distribute automatically.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "review_form", "recipient": "team@company.com", "subject": "Q1 2026 Performance Review"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Review Agent", "sub": "send_form(Q1)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Gmail", "sub": "Forms sent"},
                ],
            },
            {
                "title": "Promote Alice to Staff Engineer",
                "description": "Promotions need HR Manager + direct Manager.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "promotion", "employee": "alice@company.com", "new_title": "Staff Engineer"},
                "badge": "warning", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Review Agent", "sub": "promote(Staff Eng)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: promotion"},
                    {"type": "approver", "label": "HR Manager", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "Manager", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Gmail", "sub": "Promotion letter sent"},
                ],
            },
            {
                "title": "Salary increase ($150k -> $175k)",
                "description": "Salary changes need HR + CFO sequential approval.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"type": "salary_increase", "employee": "bob@company.com", "current": 150000, "new_salary": 175000},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Review Agent", "sub": "raise($150k -> $175k)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: salary increase"},
                    {"type": "approver", "label": "HR Manager", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "CFO", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Payroll", "sub": "Salary updated"},
                ],
            },
        ],
    },

    # ── Support Escalation Agent ─────────────────────────────────────────────
    {
        "id": "support_escalation",
        "title": "Support Escalation Agent",
        "icon": "Headphones",
        "category": "customer_service",
        "categoryLabel": "Customer Service",
        "description": "Customer complaint management. Standard complaints auto-respond, VIP customers route to CS Manager, large compensations need CFO + Legal step-up.",
        "setupInfo": [
            {"type": "connection", "name": "salesforce-prod", "detail": "Case management"},
            {"type": "connection", "name": "stripe-prod", "detail": "Compensation payments"},
            {"type": "approver", "name": "CS Manager", "detail": "VIP complaints"},
            {"type": "approver", "name": "CFO", "detail": "Large compensations"},
            {"type": "rule", "name": "VIP complaint", "detail": "specific -> CS Manager"},
            {"type": "rule", "name": "Large compensation", "detail": "all_of_n -> CFO + Legal"},
        ],
        "scenarios": [
            {
                "title": "Standard complaint: shipping delay",
                "description": "Standard issues auto-respond with template.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "standard", "customer": "user@example.com", "subject": "Shipping delay apology"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Support Agent", "sub": "auto_respond(...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Gmail", "sub": "Response sent"},
                ],
            },
            {
                "title": "VIP complaint: service outage",
                "description": "VIP customers get CS Manager attention.",
                "connection": "salesforce-prod", "action": "update_case",
                "params": {"customer_tier": "vip", "customer": "enterprise@bigcorp.com", "subject": "48h outage"},
                "badge": "warning", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "Support Agent", "sub": "escalate(VIP)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: VIP complaint"},
                    {"type": "approver", "label": "CS Manager", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Salesforce", "sub": "Case escalated"},
                ],
            },
            {
                "title": "Compensation $5,000",
                "description": "Large compensations require CFO + Legal.",
                "connection": "stripe-prod", "action": "refund",
                "params": {"type": "compensation", "amount_usd": 5000, "customer": "enterprise@bigcorp.com", "reason": "SLA breach"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Support Agent", "sub": "compensate($5k)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: large compensation"},
                    {"type": "approver", "label": "CFO", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "Legal", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "$5,000 refund issued"},
                ],
            },
        ],
    },

    # ── Account Takeover Agent ───────────────────────────────────────────────
    {
        "id": "account_takeover",
        "title": "Account Takeover Response Agent",
        "icon": "Lock",
        "category": "customer_service",
        "categoryLabel": "Customer Service",
        "description": "Account security breach response. Suspicious activity alerts auto-notify, account freezing needs Security Lead, permanent bans require Security + Legal all_of_n.",
        "setupInfo": [
            {"type": "connection", "name": "salesforce-prod", "detail": "Account management"},
            {"type": "approver", "name": "Security Lead", "detail": "Account freeze"},
            {"type": "approver", "name": "Legal", "detail": "Permanent bans"},
            {"type": "rule", "name": "Freeze account", "detail": "specific -> Security Lead"},
            {"type": "rule", "name": "Permanent ban", "detail": "all_of_n -> Security + Legal"},
        ],
        "scenarios": [
            {
                "title": "Alert: suspicious activity",
                "description": "Activity alerts auto-notify the team.",
                "connection": "slack-prod", "action": "send_message",
                "params": {"channel": "#security", "message": "Suspicious login: user@example.com from new device"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "ATO Agent", "sub": "alert(suspicious)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Slack", "sub": "Alert posted"},
                ],
            },
            {
                "title": "Freeze account",
                "description": "Account freezing needs Security Lead approval.",
                "connection": "salesforce-prod", "action": "update_case",
                "params": {"type": "freeze_account", "account_id": "ACC-12345", "reason": "Multiple failed login attempts"},
                "badge": "warning", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "ATO Agent", "sub": "freeze(ACC-12345)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: freeze account"},
                    {"type": "approver", "label": "Security Lead", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Salesforce", "sub": "Account frozen"},
                ],
            },
            {
                "title": "Permanent ban for fraud",
                "description": "Permanent bans require Security + Legal.",
                "connection": "salesforce-prod", "action": "update_case",
                "params": {"type": "permanent_ban", "account_id": "ACC-67890", "reason": "Confirmed payment fraud"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "ATO Agent", "sub": "ban(ACC-67890)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: permanent ban"},
                    {"type": "approver", "label": "Security Lead", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "Legal", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Salesforce", "sub": "Account banned"},
                ],
            },
        ],
    },

    # ── SLA Breach Agent ─────────────────────────────────────────────────────
    {
        "id": "sla_breach",
        "title": "SLA Breach Agent",
        "icon": "AlertTriangle",
        "category": "customer_service",
        "categoryLabel": "Customer Service",
        "description": "Service level breach management. Breach notifications auto-send, credits under $5k need CS Manager, large compensations require CFO + Legal step-up.",
        "setupInfo": [
            {"type": "connection", "name": "stripe-prod", "detail": "Service credits"},
            {"type": "approver", "name": "CS Manager", "detail": "Credits under $5k"},
            {"type": "approver", "name": "CFO", "detail": "Large compensations"},
            {"type": "rule", "name": "SLA credit (<$5k)", "detail": "any_one -> CS Manager"},
            {"type": "rule", "name": "SLA compensation ($5k+)", "detail": "all_of_n -> CFO + Legal"},
        ],
        "scenarios": [
            {
                "title": "SLA breach notification",
                "description": "Breach notifications auto-send to affected customers.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "notification", "customer": "client@example.com", "subject": "Service Level Update"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "SLA Agent", "sub": "notify(breach)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Gmail", "sub": "Notification sent"},
                ],
            },
            {
                "title": "Service credit $2,000",
                "description": "CS Manager reviews and approves credits.",
                "connection": "stripe-prod", "action": "credit",
                "params": {"type": "sla_credit", "amount_usd": 2000, "customer": "client@example.com"},
                "badge": "info", "badgeLabel": "any_one",
                "flow": [
                    {"type": "agent", "label": "SLA Agent", "sub": "issue_credit($2k)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: SLA credit"},
                    {"type": "approver", "label": "CS Manager", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "$2,000 credit issued"},
                ],
            },
            {
                "title": "Major compensation $50,000",
                "description": "Large SLA breach compensations need CFO + Legal.",
                "connection": "stripe-prod", "action": "credit",
                "params": {"type": "sla_credit", "amount_usd": 50000, "customer": "enterprise@bigcorp.com"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "SLA Agent", "sub": "compensate($50k)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: SLA compensation"},
                    {"type": "approver", "label": "CFO", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "Legal", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "$50,000 credit issued"},
                ],
            },
        ],
    },

    # ── Patient Data Sharing Agent ───────────────────────────────────────────
    {
        "id": "patient_data",
        "title": "Patient Data Sharing Agent",
        "icon": "Stethoscope",
        "category": "healthcare",
        "categoryLabel": "Healthcare & Clinical",
        "description": "Patient record sharing. Own doctor gets automatic access, external clinics need Doctor approval, insurance companies require Patient Rep + Doctor step-up.",
        "setupInfo": [
            {"type": "connection", "name": "gdrive-prod", "detail": "Record sharing"},
            {"type": "approver", "name": "Doctor", "detail": "External clinic shares"},
            {"type": "approver", "name": "Patient Rep", "detail": "Insurance shares"},
            {"type": "rule", "name": "External clinic", "detail": "specific -> Doctor"},
            {"type": "rule", "name": "Insurance company", "detail": "all_of_n -> Patient Rep + Doctor"},
        ],
        "scenarios": [
            {
                "title": "Share with own doctor",
                "description": "Sharing with the patient's primary doctor is automatic.",
                "connection": "gdrive-prod", "action": "share_file",
                "params": {"patient_id": "PAT-001", "recipient_type": "own_doctor", "doctor": "Dr. Smith"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Patient Data", "sub": "share(own_doctor)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Google Drive", "sub": "Records shared"},
                ],
            },
            {
                "title": "Share with external clinic",
                "description": "External sharing needs Doctor review.",
                "connection": "gdrive-prod", "action": "share_file",
                "params": {"patient_id": "PAT-001", "recipient_type": "external_clinic", "clinic": "City Hospital"},
                "badge": "info", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "Patient Data", "sub": "share(external)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: external clinic"},
                    {"type": "approver", "label": "Doctor", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Google Drive", "sub": "Records shared"},
                ],
            },
            {
                "title": "Share with insurance",
                "description": "Insurance access needs Patient Rep + Doctor.",
                "connection": "gdrive-prod", "action": "share_file",
                "params": {"patient_id": "PAT-001", "recipient_type": "insurance", "insurance_company": "HealthCare Inc"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Patient Data", "sub": "share(insurance)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: insurance share"},
                    {"type": "approver", "label": "Patient Rep", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "Doctor", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Google Drive", "sub": "Records shared"},
                ],
            },
        ],
    },

    # ── Medical Supply Agent ─────────────────────────────────────────────────
    {
        "id": "medical_supply",
        "title": "Medical Supply Agent",
        "icon": "Heart",
        "category": "healthcare",
        "categoryLabel": "Healthcare & Clinical",
        "description": "Clinical supply ordering. Standard consumables auto-order, expensive equipment needs Chief Doctor, device purchases require Chief Doctor + CFO all_of_n.",
        "setupInfo": [
            {"type": "connection", "name": "stripe-prod", "detail": "Supply purchases"},
            {"type": "approver", "name": "Chief Doctor", "detail": "Equipment orders"},
            {"type": "approver", "name": "CFO", "detail": "Device purchases"},
            {"type": "rule", "name": "Equipment ($1k-$20k)", "detail": "specific -> Chief Doctor"},
            {"type": "rule", "name": "Device ($20k+)", "detail": "all_of_n -> Chief Doctor + CFO"},
        ],
        "scenarios": [
            {
                "title": "Standard supplies ($200)",
                "description": "Consumables auto-order without approval.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"type": "medical_supply", "amount_usd": 200, "item": "Gloves and masks (bulk)", "category": "consumable"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Supply Agent", "sub": "order(consumables, $200)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Stripe", "sub": "Order placed"},
                ],
            },
            {
                "title": "MRI contrast agent ($5,000)",
                "description": "Expensive supplies need Chief Doctor review.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"type": "medical_supply", "amount_usd": 5000, "item": "MRI Contrast Agent (Gadolinium)"},
                "badge": "info", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "Supply Agent", "sub": "order(MRI contrast, $5k)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: equipment"},
                    {"type": "approver", "label": "Chief Doctor", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "Order placed"},
                ],
            },
            {
                "title": "Diagnostic device ($50,000)",
                "description": "Major equipment needs Chief Doctor + CFO.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"type": "medical_supply", "amount_usd": 50000, "item": "Portable Ultrasound System"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Supply Agent", "sub": "order(ultrasound, $50k)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: device purchase"},
                    {"type": "approver", "label": "Chief Doctor", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "CFO", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "Device ordered"},
                ],
            },
        ],
    },

    # ── Prescription Refill Agent ────────────────────────────────────────────
    {
        "id": "prescription_refill",
        "title": "Prescription Refill Agent",
        "icon": "Pill",
        "category": "healthcare",
        "categoryLabel": "Healthcare & Clinical",
        "description": "Medication refill automation. Routine refills auto-process, controlled substances need Doctor approval, dosage changes require Doctor + Pharmacist sequential.",
        "setupInfo": [
            {"type": "connection", "name": "gmail-prod", "detail": "Prescription notifications"},
            {"type": "approver", "name": "Doctor", "detail": "Controlled substances"},
            {"type": "approver", "name": "Pharmacist", "detail": "Dosage verification"},
            {"type": "rule", "name": "Controlled refill", "detail": "specific -> Doctor"},
            {"type": "rule", "name": "Dosage change", "detail": "all_of_n -> Doctor + Pharmacist"},
        ],
        "scenarios": [
            {
                "title": "Routine refill: Metformin 500mg",
                "description": "Standard medication refills process automatically.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "routine_refill", "medication": "Metformin", "dosage": "500mg", "patient": "patient@example.com"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Rx Agent", "sub": "refill(Metformin)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Pharmacy", "sub": "Refill processed"},
                ],
            },
            {
                "title": "Controlled: Adderall 20mg",
                "description": "Controlled substances require Doctor authorization.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "controlled_refill", "medication": "Adderall", "dosage": "20mg", "patient": "patient@example.com"},
                "badge": "warning", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "Rx Agent", "sub": "refill(Adderall)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: controlled substance"},
                    {"type": "approver", "label": "Doctor", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Pharmacy", "sub": "Prescription authorized"},
                ],
            },
            {
                "title": "Dosage change: Lisinopril 10mg -> 20mg",
                "description": "Dosage changes need Doctor + Pharmacist verification.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "dosage_change", "medication": "Lisinopril", "old_dosage": "10mg", "new_dosage": "20mg", "patient": "patient@example.com"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Rx Agent", "sub": "change_dosage(10->20mg)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: dosage change"},
                    {"type": "approver", "label": "Doctor", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "Pharmacist", "sub": "Guardian push -> Verify"},
                    {"type": "action", "label": "Pharmacy", "sub": "New dosage authorized"},
                ],
            },
        ],
    },

    # ── Research Data Agent ──────────────────────────────────────────────────
    {
        "id": "research_data",
        "title": "Research Data Agent",
        "icon": "Microscope",
        "category": "healthcare",
        "categoryLabel": "Healthcare & Clinical",
        "description": "Clinical research data access. Anonymized data is automatic, patient-level data needs Ethics Board, external institution sharing requires Ethics + Chief Doctor.",
        "setupInfo": [
            {"type": "connection", "name": "gdrive-prod", "detail": "Data sharing"},
            {"type": "approver", "name": "Ethics Board", "detail": "Patient data access"},
            {"type": "approver", "name": "Chief Doctor", "detail": "External sharing"},
            {"type": "rule", "name": "Patient-level data", "detail": "specific -> Ethics Board"},
            {"type": "rule", "name": "External share", "detail": "all_of_n -> Ethics + Chief Doctor"},
        ],
        "scenarios": [
            {
                "title": "Anonymized dataset",
                "description": "De-identified data access is automatic.",
                "connection": "gdrive-prod", "action": "share_file",
                "params": {"data_type": "anonymized", "study_id": "STUDY-042", "researcher": "dr.jones@research.edu"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Research Data", "sub": "access(anonymized)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Google Drive", "sub": "Dataset shared"},
                ],
            },
            {
                "title": "Patient-level clinical trial data",
                "description": "Identifiable data needs Ethics Board approval.",
                "connection": "gdrive-prod", "action": "share_file",
                "params": {"data_type": "patient_level", "study_id": "TRIAL-007", "researcher": "dr.smith@hospital.edu"},
                "badge": "warning", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "Research Data", "sub": "access(patient_level)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: patient data"},
                    {"type": "approver", "label": "Ethics Board", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Google Drive", "sub": "Data access granted"},
                ],
            },
            {
                "title": "Share with external institution",
                "description": "Cross-institutional sharing needs Ethics + Chief Doctor.",
                "connection": "gdrive-prod", "action": "share_file",
                "params": {"data_type": "external_share", "institution": "MIT Research Lab", "study_id": "COLLAB-003"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Research Data", "sub": "share(MIT)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: external share"},
                    {"type": "approver", "label": "Ethics Board", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "Chief Doctor", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Google Drive", "sub": "Data shared with MIT"},
                ],
            },
        ],
    },

    # ── Grade Override Agent ─────────────────────────────────────────────────
    {
        "id": "grade_override",
        "title": "Grade Override Agent",
        "icon": "BookOpen",
        "category": "education",
        "categoryLabel": "Education",
        "description": "Grade correction management. Administrative errors auto-fix, grade appeals need Teacher, final grade overrides require Teacher + Department Head.",
        "setupInfo": [
            {"type": "connection", "name": "gsheets-prod", "detail": "Grade sheets"},
            {"type": "approver", "name": "Teacher", "detail": "Grade appeals"},
            {"type": "approver", "name": "Department Head", "detail": "Final overrides"},
            {"type": "rule", "name": "Grade appeal", "detail": "specific -> Teacher"},
            {"type": "rule", "name": "Final override", "detail": "all_of_n -> Teacher + Dept Head"},
        ],
        "scenarios": [
            {
                "title": "Fix admin error (72 -> 78)",
                "description": "Administrative corrections auto-apply.",
                "connection": "gsheets-prod", "action": "update_sheet",
                "params": {"type": "admin_error", "student": "STU-1234", "course": "CS101", "current_grade": 72, "new_grade": 78},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Grade Agent", "sub": "fix_error(72->78)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Sheets", "sub": "Grade corrected"},
                ],
            },
            {
                "title": "Grade appeal: B -> B+",
                "description": "Student grade appeals need Teacher review.",
                "connection": "gsheets-prod", "action": "update_sheet",
                "params": {"type": "grade_appeal", "student": "STU-5678", "course": "MATH201", "current_grade": "B", "new_grade": "B+"},
                "badge": "info", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "Grade Agent", "sub": "appeal(B->B+)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: grade appeal"},
                    {"type": "approver", "label": "Teacher", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Sheets", "sub": "Grade updated"},
                ],
            },
            {
                "title": "Final grade override",
                "description": "Changing final grades needs Teacher + Department Head.",
                "connection": "gsheets-prod", "action": "update_sheet",
                "params": {"type": "final_override", "student": "STU-9012", "course": "PHY301", "current_grade": "C", "new_grade": "B-"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Grade Agent", "sub": "override(C->B-)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: final override"},
                    {"type": "approver", "label": "Teacher", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "Department Head", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Sheets", "sub": "Final grade overridden"},
                ],
            },
        ],
    },

    # ── Scholarship Agent ────────────────────────────────────────────────────
    {
        "id": "scholarship",
        "title": "Scholarship Agent",
        "icon": "Award",
        "category": "education",
        "categoryLabel": "Education",
        "description": "Scholarship lifecycle management. Applications auto-accept, award amounts under $10k need Committee, full scholarships require Rector + Committee all_of_n.",
        "setupInfo": [
            {"type": "connection", "name": "stripe-prod", "detail": "Scholarship disbursement"},
            {"type": "approver", "name": "Scholarship Committee", "detail": "Award decisions"},
            {"type": "approver", "name": "Rector", "detail": "Full scholarships"},
            {"type": "rule", "name": "Award (<$10k)", "detail": "any_one -> Committee"},
            {"type": "rule", "name": "Full scholarship", "detail": "all_of_n -> Rector + Committee"},
        ],
        "scenarios": [
            {
                "title": "Accept application",
                "description": "Application recording is automatic.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "application", "student": "applicant@university.edu", "subject": "Application received"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Scholarship", "sub": "accept_application(...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Gmail", "sub": "Confirmation sent"},
                ],
            },
            {
                "title": "Merit scholarship ($5,000)",
                "description": "Committee reviews and approves merit awards.",
                "connection": "stripe-prod", "action": "payout",
                "params": {"type": "scholarship", "amount_usd": 5000, "student": "top@university.edu"},
                "badge": "info", "badgeLabel": "any_one",
                "flow": [
                    {"type": "agent", "label": "Scholarship", "sub": "award($5k)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: scholarship award"},
                    {"type": "approver", "label": "Committee", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "$5,000 disbursed"},
                ],
            },
            {
                "title": "Full scholarship ($40,000/yr)",
                "description": "Full rides need Rector + Committee approval.",
                "connection": "stripe-prod", "action": "payout",
                "params": {"type": "full_scholarship", "amount_usd": 40000, "student": "exceptional@university.edu"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Scholarship", "sub": "full_award($40k/yr)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: full scholarship"},
                    {"type": "approver", "label": "Rector", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "Committee", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "Full scholarship awarded"},
                ],
            },
        ],
    },

    # ── Research Grant Agent ─────────────────────────────────────────────────
    {
        "id": "research_grant",
        "title": "Research Grant Agent",
        "icon": "Coins",
        "category": "education",
        "categoryLabel": "Education",
        "description": "Research fund management. Small expenditures need Department Head, medium need Rector, large grants over $50k require Rector + External Board sequential.",
        "setupInfo": [
            {"type": "connection", "name": "stripe-prod", "detail": "Grant disbursement"},
            {"type": "approver", "name": "Department Head", "detail": "Under $5k"},
            {"type": "approver", "name": "Rector", "detail": "$5k-$50k"},
            {"type": "approver", "name": "External Board", "detail": "Over $50k"},
            {"type": "rule", "name": "Grant (<$5k)", "detail": "any_one -> Dept Head"},
            {"type": "rule", "name": "Grant ($5k-$50k)", "detail": "specific -> Rector"},
            {"type": "rule", "name": "Grant ($50k+)", "detail": "all_of_n -> Rector + External Board"},
        ],
        "scenarios": [
            {
                "title": "Lab equipment ($3,000)",
                "description": "Small grant expenses need Department Head.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"type": "grant", "amount_usd": 3000, "purpose": "Lab equipment for NLP research"},
                "badge": "info", "badgeLabel": "any_one",
                "flow": [
                    {"type": "agent", "label": "Grant Agent", "sub": "spend($3k)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: small grant"},
                    {"type": "approver", "label": "Department Head", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "$3,000 disbursed"},
                ],
            },
            {
                "title": "Conference sponsorship ($25,000)",
                "description": "Medium grants go to the Rector.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"type": "grant", "amount_usd": 25000, "purpose": "NeurIPS 2026 sponsorship"},
                "badge": "warning", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "Grant Agent", "sub": "spend($25k)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: medium grant"},
                    {"type": "approver", "label": "Rector", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "$25,000 disbursed"},
                ],
            },
            {
                "title": "External collaboration ($75,000)",
                "description": "Large grants need Rector + External Board.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"type": "grant", "amount_usd": 75000, "purpose": "MIT collaboration on quantum ML"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Grant Agent", "sub": "spend($75k)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: large grant"},
                    {"type": "approver", "label": "Rector", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "External Board", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "$75,000 disbursed"},
                ],
            },
        ],
    },

    # ── Contract Signing Agent ───────────────────────────────────────────────
    {
        "id": "contract_signing",
        "title": "Contract Signing Agent",
        "icon": "FileSignature",
        "category": "legal",
        "categoryLabel": "Legal & Compliance",
        "description": "Contract automation. NDAs send automatically, service agreements need Legal review, partnership agreements require CEO + Legal all_of_n.",
        "setupInfo": [
            {"type": "connection", "name": "gmail-prod", "detail": "Contract emails"},
            {"type": "approver", "name": "Legal", "detail": "Service agreements"},
            {"type": "approver", "name": "CEO", "detail": "Partnerships"},
            {"type": "rule", "name": "Service agreement", "detail": "specific -> Legal"},
            {"type": "rule", "name": "Partnership", "detail": "all_of_n -> CEO + Legal"},
        ],
        "scenarios": [
            {
                "title": "Send standard NDA",
                "description": "Template NDAs auto-send.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "nda", "party": "partner@example.com", "subject": "Mutual NDA"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Contract Agent", "sub": "send_nda(...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Gmail + Dropbox", "sub": "NDA sent"},
                ],
            },
            {
                "title": "Service agreement",
                "description": "Service contracts need Legal review.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "service_agreement", "party": "vendor@example.com", "subject": "SaaS Service Agreement"},
                "badge": "info", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "Contract Agent", "sub": "service_agreement(...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: service agreement"},
                    {"type": "approver", "label": "Legal", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Gmail + Dropbox", "sub": "Agreement sent"},
                ],
            },
            {
                "title": "Partnership agreement",
                "description": "Strategic partnerships need CEO + Legal.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "partnership", "party": "BigTech Inc", "subject": "Strategic Partnership Agreement"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Contract Agent", "sub": "partnership(BigTech)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: partnership"},
                    {"type": "approver", "label": "CEO", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "Legal", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Gmail + Dropbox", "sub": "Partnership signed"},
                ],
            },
        ],
    },

    # ── GDPR Request Agent ───────────────────────────────────────────────────
    {
        "id": "gdpr_request",
        "title": "GDPR Request Agent",
        "icon": "ShieldCheck",
        "category": "legal",
        "categoryLabel": "Legal & Compliance",
        "description": "Data deletion request handling. Request logging is automatic, single deletions need Privacy Officer, bulk deletions require CTO + Privacy Officer step-up.",
        "setupInfo": [
            {"type": "connection", "name": "github-prod", "detail": "Data deletion jobs"},
            {"type": "approver", "name": "Privacy Officer", "detail": "Single deletions"},
            {"type": "approver", "name": "CTO", "detail": "Bulk deletions"},
            {"type": "rule", "name": "Single delete", "detail": "specific -> Privacy Officer"},
            {"type": "rule", "name": "Bulk delete", "detail": "all_of_n -> CTO + Privacy Officer"},
        ],
        "scenarios": [
            {
                "title": "Log GDPR request",
                "description": "Request intake is automatic.",
                "connection": "slack-prod", "action": "send_message",
                "params": {"channel": "#privacy", "message": "GDPR request from user@example.com"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "GDPR Agent", "sub": "log_request(...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Slack", "sub": "Request logged"},
                ],
            },
            {
                "title": "Delete single user data",
                "description": "Individual data deletion needs Privacy Officer.",
                "connection": "github-prod", "action": "deploy",
                "params": {"type": "gdpr_delete", "user_email": "user@example.com"},
                "badge": "info", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "GDPR Agent", "sub": "delete(user@...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: single delete"},
                    {"type": "approver", "label": "Privacy Officer", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Data Pipeline", "sub": "User data purged"},
                ],
            },
            {
                "title": "Bulk delete (500 records)",
                "description": "Mass deletions need CTO + Privacy Officer.",
                "connection": "github-prod", "action": "deploy",
                "params": {"type": "gdpr_bulk_delete", "count": 500, "reason": "Annual data retention cleanup"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "GDPR Agent", "sub": "bulk_delete(500)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: bulk delete"},
                    {"type": "approver", "label": "CTO", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "Privacy Officer", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Data Pipeline", "sub": "500 records purged"},
                ],
            },
        ],
    },

    # ── IP Filing Agent ──────────────────────────────────────────────────────
    {
        "id": "ip_filing",
        "title": "IP Filing Agent",
        "icon": "Lightbulb",
        "category": "legal",
        "categoryLabel": "Legal & Compliance",
        "description": "Intellectual property management. Patent drafts auto-prepare, domestic filings need Legal, international PCT applications require CEO + Legal all_of_n.",
        "setupInfo": [
            {"type": "connection", "name": "gmail-prod", "detail": "Filing communications"},
            {"type": "approver", "name": "Legal", "detail": "Domestic filings"},
            {"type": "approver", "name": "CEO", "detail": "International filings"},
            {"type": "rule", "name": "Domestic filing", "detail": "specific -> Legal"},
            {"type": "rule", "name": "International (PCT)", "detail": "all_of_n -> CEO + Legal"},
        ],
        "scenarios": [
            {
                "title": "Prepare patent draft",
                "description": "Draft preparation is automatic.",
                "connection": "slack-prod", "action": "send_message",
                "params": {"channel": "#ip", "message": "Patent draft prepared: Efficient Approval Graph Algorithm"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "IP Agent", "sub": "prepare_draft(...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Dropbox", "sub": "Draft saved"},
                ],
            },
            {
                "title": "File domestic patent",
                "description": "Domestic patent filings need Legal review.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "domestic_filing", "title": "Approval Graph Algorithm", "jurisdiction": "US"},
                "badge": "info", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "IP Agent", "sub": "file_domestic(US)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: domestic filing"},
                    {"type": "approver", "label": "Legal", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "USPTO", "sub": "Patent filed"},
                ],
            },
            {
                "title": "International patent (PCT)",
                "description": "International filings need CEO + Legal.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "international_filing", "title": "Approval Graph Algorithm", "jurisdictions": ["US", "EU", "JP"]},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "IP Agent", "sub": "file_international(PCT)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: international filing"},
                    {"type": "approver", "label": "CEO", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "Legal", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "WIPO", "sub": "PCT application filed"},
                ],
            },
        ],
    },

    # ── Maintenance Request Agent ────────────────────────────────────────────
    {
        "id": "maintenance_request",
        "title": "Maintenance Request Agent",
        "icon": "Wrench",
        "category": "real_estate",
        "categoryLabel": "Real Estate",
        "description": "Building maintenance management. Small repairs under $500 auto-approve, medium need Building Manager, major repairs require Property Owner step-up. Emergencies bypass blackout.",
        "setupInfo": [
            {"type": "connection", "name": "stripe-prod", "detail": "Repair payments"},
            {"type": "approver", "name": "Building Manager", "detail": "Medium repairs"},
            {"type": "approver", "name": "Property Owner", "detail": "Major repairs"},
            {"type": "rule", "name": "Medium ($500-$5k)", "detail": "any_one -> Building Manager"},
            {"type": "rule", "name": "Major ($5k+)", "detail": "all_of_n -> Manager + Owner"},
        ],
        "scenarios": [
            {
                "title": "Fix leaky faucet ($200)",
                "description": "Small repairs auto-approve instantly.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"type": "maintenance", "amount_usd": 200, "description": "Fix leaky faucet Unit 4B"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Maintenance", "sub": "repair($200)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Stripe", "sub": "$200 authorized"},
                ],
            },
            {
                "title": "HVAC replacement ($3,000)",
                "description": "Medium repairs need Building Manager approval.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"type": "maintenance", "amount_usd": 3000, "description": "Replace HVAC unit Building A"},
                "badge": "info", "badgeLabel": "any_one",
                "flow": [
                    {"type": "agent", "label": "Maintenance", "sub": "repair($3k)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: medium maintenance"},
                    {"type": "approver", "label": "Building Manager", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "$3,000 authorized"},
                ],
            },
            {
                "title": "Major roof repair ($15,000)",
                "description": "Large repairs need Building Manager + Property Owner.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"type": "maintenance", "amount_usd": 15000, "description": "Roof repair Building C"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Maintenance", "sub": "repair($15k)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: major maintenance"},
                    {"type": "approver", "label": "Building Manager", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "Property Owner", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "$15,000 authorized"},
                ],
            },
        ],
    },

    # ── Tenant Screening Agent ───────────────────────────────────────────────
    {
        "id": "tenant_screening",
        "title": "Tenant Screening Agent",
        "icon": "UserSearch",
        "category": "real_estate",
        "categoryLabel": "Real Estate",
        "description": "Tenant application management. Credit checks auto-run, eviction history needs Property Manager review, criminal background checks require Property Manager + Legal.",
        "setupInfo": [
            {"type": "connection", "name": "salesforce-prod", "detail": "Application tracking"},
            {"type": "approver", "name": "Property Manager", "detail": "Eviction history"},
            {"type": "approver", "name": "Legal", "detail": "Criminal checks"},
            {"type": "rule", "name": "Eviction history", "detail": "specific -> Property Manager"},
            {"type": "rule", "name": "Criminal check", "detail": "all_of_n -> Manager + Legal"},
        ],
        "scenarios": [
            {
                "title": "Credit check",
                "description": "Standard credit checks run automatically.",
                "connection": "salesforce-prod", "action": "create_ticket",
                "params": {"check_type": "credit", "applicant": "John Doe", "unit": "Apt 3A"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Screening", "sub": "credit_check(John Doe)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Salesforce", "sub": "Check completed"},
                ],
            },
            {
                "title": "Eviction history review",
                "description": "Applicants with eviction records need manager review.",
                "connection": "salesforce-prod", "action": "create_ticket",
                "params": {"check_type": "eviction_history", "applicant": "Jane Smith", "unit": "Apt 5B"},
                "badge": "warning", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "Screening", "sub": "eviction_check(...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: eviction history"},
                    {"type": "approver", "label": "Property Manager", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Salesforce", "sub": "Review completed"},
                ],
            },
            {
                "title": "Criminal background check",
                "description": "Criminal checks need Property Manager + Legal.",
                "connection": "salesforce-prod", "action": "create_ticket",
                "params": {"check_type": "criminal_check", "applicant": "Bob Wilson", "unit": "Apt 2C"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Screening", "sub": "criminal_check(...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: criminal check"},
                    {"type": "approver", "label": "Property Manager", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "Legal", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Salesforce", "sub": "Check completed"},
                ],
            },
        ],
    },

    # ── Content Moderation Agent ─────────────────────────────────────────────
    {
        "id": "content_moderation",
        "title": "Content Moderation Agent",
        "icon": "MessageSquare",
        "category": "media",
        "categoryLabel": "Media & Content",
        "description": "Platform content moderation. Spam auto-removes, suspicious content routes to Moderator, account bans need Senior Moderator + Legal step-up.",
        "setupInfo": [
            {"type": "connection", "name": "slack-prod", "detail": "Moderation alerts"},
            {"type": "approver", "name": "Moderator", "detail": "Content review"},
            {"type": "approver", "name": "Senior Moderator", "detail": "Account bans"},
            {"type": "approver", "name": "Legal", "detail": "Ban compliance"},
            {"type": "rule", "name": "Suspicious content", "detail": "any_one -> Moderator"},
            {"type": "rule", "name": "Account ban", "detail": "all_of_n -> Sr. Moderator + Legal"},
        ],
        "scenarios": [
            {
                "title": "Auto-remove spam",
                "description": "Detected spam is automatically removed.",
                "connection": "slack-prod", "action": "send_message",
                "params": {"channel": "#moderation", "message": "Spam removed: POST-12345"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Mod Agent", "sub": "remove_spam(...)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Platform", "sub": "Content removed"},
                ],
            },
            {
                "title": "Flag suspicious content",
                "description": "Borderline content needs Moderator review.",
                "connection": "slack-prod", "action": "send_message",
                "params": {"type": "suspicious_content", "content_id": "POST-67890", "reason": "Potential misinformation"},
                "badge": "info", "badgeLabel": "any_one",
                "flow": [
                    {"type": "agent", "label": "Mod Agent", "sub": "flag(POST-67890)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: suspicious content"},
                    {"type": "approver", "label": "Moderator", "sub": "Guardian push -> Review"},
                    {"type": "action", "label": "Platform", "sub": "Content reviewed"},
                ],
            },
            {
                "title": "Permanent account ban",
                "description": "Account bans need Senior Moderator + Legal.",
                "connection": "slack-prod", "action": "send_message",
                "params": {"type": "account_ban", "account_id": "USER-99999", "reason": "Repeated TOS violations"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Mod Agent", "sub": "ban(USER-99999)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: account ban"},
                    {"type": "approver", "label": "Senior Moderator", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "Legal", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Platform", "sub": "Account banned"},
                ],
            },
        ],
    },

    # ── Licensing Agent ──────────────────────────────────────────────────────
    {
        "id": "licensing",
        "title": "Licensing Agent",
        "icon": "FileText",
        "category": "media",
        "categoryLabel": "Media & Content",
        "description": "Content licensing management. Personal licenses auto-issue, commercial licenses need Legal review, major media deals over $100k require CEO + Legal all_of_n.",
        "setupInfo": [
            {"type": "connection", "name": "stripe-prod", "detail": "License payments"},
            {"type": "approver", "name": "Legal", "detail": "Commercial licenses"},
            {"type": "approver", "name": "CEO", "detail": "Major deals"},
            {"type": "rule", "name": "Commercial license", "detail": "specific -> Legal"},
            {"type": "rule", "name": "Major deal ($100k+)", "detail": "all_of_n -> CEO + Legal"},
        ],
        "scenarios": [
            {
                "title": "Personal license",
                "description": "Personal use licenses auto-issue.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"type": "personal_license", "amount_usd": 29, "licensee": "user@example.com"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "License Agent", "sub": "issue(personal)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Stripe", "sub": "License issued"},
                ],
            },
            {
                "title": "Commercial license ($5,000)",
                "description": "Commercial use needs Legal review.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"type": "commercial_license", "amount_usd": 5000, "licensee": "MediaCorp Ltd"},
                "badge": "info", "badgeLabel": "specific",
                "flow": [
                    {"type": "agent", "label": "License Agent", "sub": "issue(commercial, $5k)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: commercial license"},
                    {"type": "approver", "label": "Legal", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "Commercial license issued"},
                ],
            },
            {
                "title": "Major media deal ($250,000)",
                "description": "Large deals need CEO + Legal.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"type": "major_deal", "amount_usd": 250000, "licensee": "Global Media Inc"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "License Agent", "sub": "deal($250k, Global Media)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: major deal"},
                    {"type": "approver", "label": "CEO", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "Legal", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "Deal signed"},
                ],
            },
        ],
    },

    # ── Environmental Incident Agent ─────────────────────────────────────────
    {
        "id": "environmental_incident",
        "title": "Environmental Incident Agent",
        "icon": "Leaf",
        "category": "energy",
        "categoryLabel": "Energy & Environment",
        "description": "Environmental compliance management. Monitoring data auto-logs, minor spills auto-notify, major incidents require CEO + Environmental Officer all_of_n for regulatory reporting.",
        "setupInfo": [
            {"type": "connection", "name": "gmail-prod", "detail": "Incident reports"},
            {"type": "approver", "name": "CEO", "detail": "Major incidents"},
            {"type": "approver", "name": "Environmental Officer", "detail": "Co-approves major incidents"},
            {"type": "rule", "name": "Major incident", "detail": "all_of_n -> CEO + Environmental Officer"},
        ],
        "scenarios": [
            {
                "title": "Routine monitoring log",
                "description": "Environmental monitoring auto-logs.",
                "connection": "slack-prod", "action": "send_message",
                "params": {"channel": "#environment", "message": "Daily readings: all parameters within limits"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Env Agent", "sub": "log_monitoring()"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Slack", "sub": "Data logged"},
                ],
            },
            {
                "title": "Minor chemical spill",
                "description": "Small spills auto-notify with containment protocol.",
                "connection": "slack-prod", "action": "send_message",
                "params": {"channel": "#safety", "message": "Minor spill in Lab B - containment activated"},
                "badge": "info", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Env Agent", "sub": "report(minor_spill)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Slack", "sub": "Team notified"},
                ],
            },
            {
                "title": "Major containment breach",
                "description": "Critical incidents need CEO + Environmental Officer.",
                "connection": "gmail-prod", "action": "send_email",
                "params": {"type": "major_incident", "incident_type": "Chemical containment breach", "location": "Building C Tank 3"},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Env Agent", "sub": "major_incident(breach)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: major incident"},
                    {"type": "approver", "label": "CEO", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "Environmental Officer", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Gmail", "sub": "Regulatory report filed"},
                ],
            },
        ],
    },

    # ── Renewable Energy Purchase Agent ──────────────────────────────────────
    {
        "id": "renewable_energy",
        "title": "Renewable Energy Purchase Agent",
        "icon": "Zap",
        "category": "energy",
        "categoryLabel": "Energy & Environment",
        "description": "Renewable energy procurement. Small credit purchases auto-execute, medium purchases need CFO, long-term PPA agreements require CEO + CFO all_of_n.",
        "setupInfo": [
            {"type": "connection", "name": "stripe-prod", "detail": "Energy purchases"},
            {"type": "approver", "name": "CFO", "detail": "Medium purchases"},
            {"type": "approver", "name": "CEO", "detail": "Long-term agreements"},
            {"type": "rule", "name": "Medium purchase ($10k-$100k)", "detail": "any_one -> CFO"},
            {"type": "rule", "name": "Long-term PPA", "detail": "all_of_n -> CEO + CFO"},
        ],
        "scenarios": [
            {
                "title": "Small solar credits ($8,000)",
                "description": "Small energy purchases auto-execute.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"type": "energy_purchase", "amount_usd": 8000, "quantity": 100, "source": "solar"},
                "badge": "success", "badgeLabel": "auto",
                "flow": [
                    {"type": "agent", "label": "Energy Agent", "sub": "purchase(100 MWh, $8k)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "No rule matched"},
                    {"type": "action", "label": "Stripe", "sub": "Credits purchased"},
                ],
            },
            {
                "title": "Wind credits ($75,000)",
                "description": "Medium purchases need CFO review.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"type": "energy_purchase", "amount_usd": 75000, "quantity": 1000, "source": "wind"},
                "badge": "info", "badgeLabel": "any_one",
                "flow": [
                    {"type": "agent", "label": "Energy Agent", "sub": "purchase(1000 MWh, $75k)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: medium purchase"},
                    {"type": "approver", "label": "CFO", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "Credits purchased"},
                ],
            },
            {
                "title": "5-year PPA agreement ($500k)",
                "description": "Long-term power purchase agreements need CEO + CFO.",
                "connection": "stripe-prod", "action": "charge",
                "params": {"type": "ppa_agreement", "amount_usd": 500000, "years": 5, "annual_mwh": 5000},
                "badge": "danger", "badgeLabel": "all_of_n",
                "flow": [
                    {"type": "agent", "label": "Energy Agent", "sub": "ppa(5yr, $500k)"},
                    {"type": "platform", "label": "ApprovalKit", "sub": "Rule: long-term PPA"},
                    {"type": "approver", "label": "CEO", "sub": "Guardian push -> Approve"},
                    {"type": "approver", "label": "CFO", "sub": "Guardian push -> Approve"},
                    {"type": "action", "label": "Stripe", "sub": "PPA agreement signed"},
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

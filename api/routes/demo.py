"""
Demo Seed & Catalog Endpoint
=============================
POST   /api/v1/demo/seed          — create connections, approvers, rules for demo agents
GET    /api/v1/demo/agents        — return the 10 demo agent catalog
DELETE /api/v1/demo/seed          — remove all demo-created resources

10 curated demo agents across 6 categories, each with rich scenarios
and approval flows powered by ApprovalKit.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel as BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.approver import Approver
from api.models.connection import ServiceConnection
from api.models.rule import Rule, RuleApprover, ApprovalModel, TimeoutAction
from api.models.workspace import Workspace
from api.middleware.workspace import get_current_workspace

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

# ── Seed Data ─────────────────────────────────────────────────────────────────

CONNECTIONS = [
    {"name": "Stripe Production",  "service": "stripe",  "slug": "stripe-prod",
     "actions": ["charge", "refund", "payout", "credit", "vendor_payment"]},
    {"name": "Slack Production",   "service": "slack",   "slug": "slack-prod",
     "actions": ["send_message"]},
    {"name": "Gmail Production",   "service": "gmail",   "slug": "gmail-prod",
     "actions": ["send_email"]},
    {"name": "GitHub Production",  "service": "github",  "slug": "github-prod",
     "actions": ["add_member", "remove_member", "deploy", "lock_repo", "revoke_tokens", "merge_pr"],
},
    {"name": "GitHub Main",        "service": "github",  "slug": "github-main",
     "actions": ["deploy", "rollback"],
},
    {"name": "Google Drive Production", "service": "google-drive", "slug": "google-drive-prod",
     "actions": ["share"]},
    {"name": "Salesforce Production", "service": "salesforce", "slug": "salesforce-prod",
     "actions": ["update_case"]},
]

APPROVERS = [
    # Finance & General
    {"name": "CFO",              "email": "cfo@demo.approvalkit.io",
     "auth0_user_id": "demo|cfo",              "role": "cfo"},
    {"name": "Manager",          "email": "manager@demo.approvalkit.io",
     "auth0_user_id": "demo|manager",          "role": "manager"},
    {"name": "CEO",              "email": "ceo@demo.approvalkit.io",
     "auth0_user_id": "demo|ceo",              "role": "ceo"},
    {"name": "Legal",            "email": "legal@demo.approvalkit.io",
     "auth0_user_id": "demo|legal",            "role": "legal"},
    # DevOps
    {"name": "Maintainer",       "email": "maintainer@demo.approvalkit.io",
     "auth0_user_id": "demo|maintainer",       "role": "maintainer"},
    {"name": "Lead Engineer",    "email": "lead_eng@demo.approvalkit.io",
     "auth0_user_id": "demo|lead_engineer",    "role": "lead_engineer"},
    {"name": "On-Call Engineer",  "email": "oncall@demo.approvalkit.io",
     "auth0_user_id": "demo|oncall",           "role": "oncall_engineer"},
    {"name": "Security Lead",    "email": "security_lead@demo.approvalkit.io",
     "auth0_user_id": "demo|security_lead",    "role": "security_lead"},
    {"name": "CTO",              "email": "cto@demo.approvalkit.io",
     "auth0_user_id": "demo|cto",              "role": "cto"},
    # HR
    {"name": "HR Manager",       "email": "hr_manager@demo.approvalkit.io",
     "auth0_user_id": "demo|hr_manager",       "role": "hr_manager"},
    {"name": "IT Manager",       "email": "it_manager@demo.approvalkit.io",
     "auth0_user_id": "demo|it_manager",       "role": "it_manager"},
    # Customer Service
    {"name": "CS Manager",       "email": "cs_manager@demo.approvalkit.io",
     "auth0_user_id": "demo|cs_manager",       "role": "cs_manager"},
    # Healthcare
    {"name": "Doctor",           "email": "doctor@demo.approvalkit.io",
     "auth0_user_id": "demo|doctor",           "role": "doctor"},
    {"name": "Chief Doctor",     "email": "chief_doctor@demo.approvalkit.io",
     "auth0_user_id": "demo|chief_doctor",     "role": "chief_doctor"},
    {"name": "Pharmacist",       "email": "pharmacist@demo.approvalkit.io",
     "auth0_user_id": "demo|pharmacist",       "role": "pharmacist"},
    {"name": "Ethics Board",     "email": "ethics@demo.approvalkit.io",
     "auth0_user_id": "demo|ethics_board",     "role": "ethics_board"},
    {"name": "Patient Rep",      "email": "patient_rep@demo.approvalkit.io",
     "auth0_user_id": "demo|patient_rep",      "role": "patient_rep"},
    # Legal / Privacy
    {"name": "Privacy Officer",  "email": "privacy@demo.approvalkit.io",
     "auth0_user_id": "demo|privacy",          "role": "privacy_officer"},
    # Travel / Research
    {"name": "VP Operations",    "email": "vp_ops@demo.approvalkit.io",
     "auth0_user_id": "demo|vp_ops",           "role": "vp"},
    {"name": "Principal Investigator", "email": "pi@demo.approvalkit.io",
     "auth0_user_id": "demo|pi",               "role": "pi"},
    {"name": "Department Head",  "email": "dept_head@demo.approvalkit.io",
     "auth0_user_id": "demo|dept_head",        "role": "dept_head"},
    # Open Source
    {"name": "Maintainer 2",    "email": "maintainer2@demo.approvalkit.io",
     "auth0_user_id": "demo|maintainer2",      "role": "maintainer2"},
    {"name": "Maintainer 3",    "email": "maintainer3@demo.approvalkit.io",
     "auth0_user_id": "demo|maintainer3",      "role": "maintainer3"},
]


def _build_rules(ar: dict[str, uuid.UUID]) -> list[dict]:
    """Build all rules for the 10 demo agents. `ar` maps role → approver UUID."""
    def c(field: str, op: str, value: Any) -> dict:
        return {"field": field, "operator": op, "value": value}

    return [
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # EXPENSE APPROVAL AGENT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        {
            "name": "[Expense] Medium ($500–$4999)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Expense ${amount_usd} — {category}: {description}",
            "conditions": [c("type", "eq", "expense"), c("amount_usd", "gte", 500), c("amount_usd", "lt", 5000)],
            "approver_roles": ["manager"],
            "partial_approval": True,
            "priority": 15,
        },
        {
            "name": "[Expense] Large ($5000+) — CFO Step-up",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "LARGE expense ${amount_usd} — {category}: {description}",
            "conditions": [c("type", "eq", "expense"), c("amount_usd", "gte", 5000)],
            "approver_roles": ["manager", "cfo"],
            "partial_approval": True,
            "priority": 25,
        },

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # RELEASE MANAGER AGENT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        {
            "name": "[Release] Production deploy",
            "connection": "github-main", "action": "deploy",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Deploy {ref} to {environment} ({service})",
            "conditions": [c("environment", "eq", "production")],
            "approver_roles": ["maintainer"],
            "priority": 20,
        },
        {
            "name": "[Release] Hotfix deploy",
            "connection": "github-main", "action": "deploy",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 120,
            "context_template": "HOTFIX {ref} to production ({service})",
            "conditions": [c("type", "eq", "hotfix")],
            "approver_roles": ["oncall_engineer"],
            "priority": 40,
        },
        {
            "name": "[Release] Production rollback",
            "connection": "github-main", "action": "rollback",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 120,
            "context_template": "ROLLBACK {env} to {version} — {reason}",
            "conditions": [c("env", "eq", "production")],
            "approver_roles": ["lead_engineer"],
            "priority": 30,
        },

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # SECURITY INCIDENT AGENT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        {
            "name": "[Security] Lock repository",
            "connection": "github-prod", "action": "lock_repo",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 300,
            "context_template": "Lock repo {repo} — {reason}",
            "conditions": [],
            "approver_roles": ["security_lead"],
            "priority": 20,
        },
        {
            "name": "[Security] Revoke production tokens",
            "connection": "github-prod", "action": "revoke_tokens",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 300,
            "context_template": "CRITICAL: Revoke {scope} tokens — {reason}",
            "conditions": [],
            "approver_roles": ["cto", "security_lead"],
            "priority": 40,
        },

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ACCOUNT TAKEOVER AGENT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        {
            "name": "[ATO] Freeze account",
            "connection": "salesforce-prod", "action": "update_case",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 180,
            "context_template": "Freeze account {email} — {reason}",
            "conditions": [c("type", "eq", "account_freeze")],
            "approver_roles": ["security_lead"],
            "priority": 30,
        },
        {
            "name": "[ATO] Permanent ban",
            "connection": "salesforce-prod", "action": "update_case",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "PERMANENT BAN: {email} — {reason}",
            "conditions": [c("type", "eq", "permanent_ban")],
            "approver_roles": ["security_lead", "legal"],
            "priority": 40,
        },
        {
            "name": "[ATO] Compensation credit ($100+)",
            "connection": "stripe-prod", "action": "credit",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 300,
            "context_template": "Compensation ${amount_usd} for {customer} — {reason}",
            "conditions": [c("amount_usd", "gte", 100)],
            "approver_roles": ["cs_manager"],
            "priority": 15,
        },

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # RECRUITMENT AGENT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        {
            "name": "[HR] Offer letter",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Offer letter to {recipient}: {subject}",
            "conditions": [c("type", "eq", "offer_letter")],
            "approver_roles": ["hr_manager"],
            "priority": 20,
        },
        {
            "name": "[HR] High salary package ($180k+)",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "Salary package ${salary_usd}: {subject}",
            "conditions": [c("type", "eq", "offer_letter"), c("salary_usd", "gte", 180000)],
            "approver_roles": ["hr_manager", "cfo"],
            "priority": 30,
        },
        {
            "name": "[HR] Termination notice",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "TERMINATION: {recipient}",
            "conditions": [c("type", "eq", "termination")],
            "approver_roles": ["hr_manager", "ceo"],
            "priority": 40,
        },
        {
            "name": "[HR] GitHub add member",
            "connection": "github-prod", "action": "add_member",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 300,
            "context_template": "Add {username} to {org} as {role}",
            "conditions": [c("role", "eq", "member")],
            "approver_roles": ["it_manager"],
            "priority": 10,
        },
        {
            "name": "[HR] GitHub add admin",
            "connection": "github-prod", "action": "add_member",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "Add {username} to {org} as ADMIN",
            "conditions": [c("role", "eq", "admin")],
            "approver_roles": ["it_manager", "cto"],
            "priority": 25,
        },

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ACCESS PROVISIONING AGENT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        {
            "name": "[Access] Standard access",
            "connection": "github-prod", "action": "add_member",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 300,
            "context_template": "Grant standard access to {username} in {org}",
            "conditions": [c("role", "eq", "member"), c("system", "eq", "github")],
            "approver_roles": ["it_manager"],
            "priority": 10,
        },
        {
            "name": "[Access] Admin privileges",
            "connection": "github-prod", "action": "add_member",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Grant ADMIN access to {username}",
            "conditions": [c("role", "eq", "admin")],
            "approver_roles": ["cto"],
            "priority": 25,
        },
        {
            "name": "[Access] Financial system",
            "connection": "github-prod", "action": "add_member",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "Grant FINANCIAL system access to {username}",
            "conditions": [c("system", "eq", "financial")],
            "approver_roles": ["cfo", "cto"],
            "priority": 35,
        },
        {
            "name": "[Access] Offboarding revoke",
            "connection": "github-prod", "action": "remove_member",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Revoke all access for {username} — {reason}",
            "conditions": [c("reason", "eq", "offboarding")],
            "approver_roles": ["hr_manager"],
            "priority": 15,
        },

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PATIENT DATA SHARING AGENT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        {
            "name": "[Patient] Share with external clinic",
            "connection": "google-drive-prod", "action": "share",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Share patient {patient_id} records with {recipient_name}",
            "conditions": [c("recipient_type", "eq", "external_clinic")],
            "approver_roles": ["doctor"],
            "priority": 20,
        },
        {
            "name": "[Patient] Share with insurance",
            "connection": "google-drive-prod", "action": "share",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "Share patient {patient_id} records with insurance: {recipient_name}",
            "conditions": [c("recipient_type", "eq", "insurance")],
            "approver_roles": ["patient_rep", "doctor"],
            "priority": 35,
        },
        {
            "name": "[Patient] Share for research",
            "connection": "google-drive-prod", "action": "share",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "Share patient data for research: {purpose}",
            "conditions": [c("recipient_type", "eq", "research")],
            "approver_roles": ["ethics_board", "chief_doctor"],
            "priority": 40,
        },

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # PRESCRIPTION REFILL AGENT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        {
            "name": "[Rx] Controlled substance refill",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Refill {medication} {dosage} for patient {patient_id}",
            "conditions": [c("type", "eq", "controlled_refill")],
            "approver_roles": ["doctor"],
            "priority": 25,
        },
        {
            "name": "[Rx] Dosage change",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "Dosage change: {medication} → {dosage} for {patient_id}",
            "conditions": [c("type", "eq", "dosage_change")],
            "approver_roles": ["doctor", "pharmacist"],
            "priority": 30,
        },
        {
            "name": "[Rx] New prescription",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "New Rx: {medication} {dosage} for {patient_id}",
            "conditions": [c("type", "eq", "new_prescription")],
            "approver_roles": ["doctor"],
            "priority": 20,
        },

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # GDPR REQUEST AGENT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        {
            "name": "[GDPR] Single user deletion",
            "connection": "github-prod", "action": "deploy",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Delete data for {subject_email} — scope: {scope}",
            "conditions": [c("type", "eq", "gdpr_deletion"), c("is_bulk", "eq", False)],
            "approver_roles": ["privacy_officer"],
            "priority": 20,
        },
        {
            "name": "[GDPR] Bulk deletion (10+ users)",
            "connection": "github-prod", "action": "deploy",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "BULK deletion: {subject_email} + others — scope: {scope}",
            "conditions": [c("type", "eq", "gdpr_deletion"), c("is_bulk", "eq", True)],
            "approver_roles": ["cto", "privacy_officer"],
            "priority": 35,
        },
        {
            "name": "[GDPR] Cross-border transfer",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "Cross-border transfer to {destination} — basis: {legal_basis}",
            "conditions": [c("type", "eq", "cross_border_transfer")],
            "approver_roles": ["legal", "privacy_officer"],
            "priority": 40,
        },

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # API KEY ROTATION AGENT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        {
            "name": "[KeyRotation] Emergency rotation",
            "connection": "github-prod", "action": "deploy",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 180,
            "context_template": "EMERGENCY rotate {service} key — {reason}",
            "conditions": [c("type", "eq", "key_rotation"), c("urgency", "eq", "emergency")],
            "approver_roles": ["security_lead"],
            "priority": 30,
        },
        {
            "name": "[KeyRotation] Third-party key",
            "connection": "github-prod", "action": "deploy",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Rotate 3rd-party {service} key — {reason}",
            "conditions": [c("type", "eq", "key_rotation"), c("is_third_party", "eq", True)],
            "approver_roles": ["cto"],
            "priority": 25,
        },
        {
            "name": "[KeyRotation] Full rotation (all keys)",
            "connection": "github-prod", "action": "deploy",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 600,
            "context_template": "FULL KEY ROTATION — {scope} — {reason}",
            "conditions": [c("type", "eq", "key_rotation"), c("migration_name", "eq", "rotate_all_keys")],
            "approver_roles": ["cto", "security_lead"],
            "priority": 40,
        },

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # FINANCE AGENT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        {
            "name": "[Finance] Medium payment ($500–$4999)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Payment ${amount_usd} to {customer} — {description}",
            "conditions": [c("amount_usd", "gte", 500), c("amount_usd", "lt", 5000)],
            "approver_roles": ["manager"],
            "priority": 14,
        },
        {
            "name": "[Finance] Large payment ($5000+)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "LARGE payment ${amount_usd} to {customer}",
            "conditions": [c("amount_usd", "gte", 5000)],
            "approver_roles": ["cfo"],
            "priority": 24,
        },

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # TRAVELOPS AGENT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        {
            "name": "[Travel] Flight $500–$2000",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "Flight booking ${amount_usd}: {description}",
            "conditions": [c("type", "eq", "travel_flight"), c("amount_usd", "gte", 500), c("amount_usd", "lt", 2000)],
            "approver_roles": ["manager"],
            "priority": 16,
        },
        {
            "name": "[Travel] Flight $2000–$5000 or business class",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Premium travel ${amount_usd}: {description}",
            "conditions": [c("type", "eq", "travel_flight"), c("amount_usd", "gte", 2000), c("amount_usd", "lt", 5000)],
            "approver_roles": ["vp"],
            "priority": 26,
        },
        {
            "name": "[Travel] Flight $5000+ (CFO required)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 900,
            "context_template": "LUXURY travel ${amount_usd}: {description}",
            "conditions": [c("type", "eq", "travel_flight"), c("amount_usd", "gte", 5000)],
            "approver_roles": ["cfo"],
            "priority": 36,
        },
        {
            "name": "[Travel] Hotel suite (CFO required)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Hotel suite ${amount_usd}: {description}",
            "conditions": [c("type", "eq", "travel_hotel"), c("room_type", "eq", "suite")],
            "approver_roles": ["cfo"],
            "priority": 32,
        },

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # OPEN SOURCE AGENT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        {
            "name": "[OSS] Feature PR merge (2-of-3)",
            "connection": "github-prod", "action": "merge_pr",
            "model": ApprovalModel.K_OF_N, "timeout_seconds": 900,
            "k_value": 2,
            "context_template": "Merge feature PR #{pr_number} in {repo}",
            "conditions": [c("type", "eq", "feature")],
            "approver_roles": ["maintainer", "maintainer2", "maintainer3"],
            "priority": 20,
        },
        {
            "name": "[OSS] Release (2-of-3 maintainers)",
            "connection": "github-prod", "action": "deploy",
            "model": ApprovalModel.K_OF_N, "timeout_seconds": 900,
            "k_value": 2,
            "context_template": "Create release {ref}: {notes}",
            "conditions": [c("type", "eq", "release")],
            "approver_roles": ["maintainer", "maintainer2", "maintainer3"],
            "priority": 25,
        },
        {
            "name": "[OSS] npm publish (ALL maintainers)",
            "connection": "github-prod", "action": "deploy",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "PUBLISH to npm: {ref}",
            "conditions": [c("type", "eq", "release"), c("publish_npm", "eq", True)],
            "approver_roles": ["maintainer", "maintainer2", "maintainer3"],
            "priority": 40,
        },
        {
            "name": "[OSS] Bounty payment ($200+)",
            "connection": "stripe-prod", "action": "payout",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Bounty ${amount_usd} to {customer}: {description}",
            "conditions": [c("type", "eq", "bounty"), c("amount_usd", "gte", 200)],
            "approver_roles": ["cfo"],
            "priority": 22,
        },

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # RESEARCH AGENT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        {
            "name": "[Research] Compute $500–$5000 (PI approval)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Compute ${amount_usd}: {description}",
            "conditions": [c("type", "eq", "compute"), c("amount_usd", "gte", 500), c("amount_usd", "lt", 5000)],
            "approver_roles": ["pi"],
            "priority": 17,
        },
        {
            "name": "[Research] Compute $5000+ (PI + Dept Head)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "LARGE compute ${amount_usd}: {description}",
            "conditions": [c("type", "eq", "compute"), c("amount_usd", "gte", 5000)],
            "approver_roles": ["pi", "dept_head"],
            "priority": 34,
        },
        {
            "name": "[Research] Dataset purchase under $1000",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 600,
            "context_template": "Dataset ${amount_usd}: {description}",
            "conditions": [c("type", "eq", "dataset_purchase"), c("amount_usd", "lt", 1000)],
            "approver_roles": ["pi"],
            "priority": 15,
        },
        {
            "name": "[Research] Dataset purchase $1000+ (PI + CFO)",
            "connection": "stripe-prod", "action": "charge",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "LARGE dataset ${amount_usd}: {description}",
            "conditions": [c("type", "eq", "dataset_purchase"), c("amount_usd", "gte", 1000)],
            "approver_roles": ["pi", "cfo"],
            "priority": 30,
        },

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # COMMS AGENT
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        {
            "name": "[Comms] External email",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.ANY_ONE, "timeout_seconds": 300,
            "context_template": "External email to {recipient}: {subject}",
            "conditions": [c("type", "eq", "external")],
            "approver_roles": ["manager"],
            "priority": 18,
        },
        {
            "name": "[Comms] Mass email (10+ recipients)",
            "connection": "gmail-prod", "action": "send_email",
            "model": ApprovalModel.ALL_OF_N, "timeout_seconds": 900,
            "context_template": "MASS EMAIL to {recipient_count} recipients: {subject}",
            "conditions": [c("recipient_count", "gte", 10)],
            "approver_roles": ["manager", "ceo"],
            "priority": 38,
        },

        # ── Shared: Slack rules ───────────────────────────────────────────────
        {
            "name": "[Shared] Slack #security channel",
            "connection": "slack-prod", "action": "send_message",
            "model": ApprovalModel.SPECIFIC, "timeout_seconds": 300,
            "context_template": "Post to {channel}: {message}",
            "conditions": [c("channel", "eq", "#security")],
            "approver_roles": ["security_lead"],
            "priority": 5,
        },
    ]


# ── Agent Catalog ─────────────────────────────────────────────────────────────

def _build_agent_catalog() -> list[dict]:
    """Build the 10 demo agent catalog with scenarios and flow diagrams."""

    def flow(*steps: tuple[str, str, str]) -> list[dict]:
        return [{"type": t, "label": l, "sub": s} for t, l, s in steps]

    return [
        # ──────────────────────────────────────────────────────────────────────
        # 1. EXPENSE APPROVAL AGENT
        # ──────────────────────────────────────────────────────────────────────
        {
            "id": "expense",
            "title": "Expense Approval Agent",
            "icon": "CreditCard",
            "category": "finance",
            "categoryLabel": "Commerce & Finance",
            "description": "Autonomous expense management agent that handles the full lifecycle of employee spending. When employees report needs — broken equipment, upcoming travel, team events — the agent evaluates the situation, determines the appropriate expense category and amount, and submits it through ApprovalKit. Expenses under $500 auto-approve instantly. $500–$5,000 requires manager sign-off via Guardian push notification. Above $5,000 triggers a step-up to dual approval (Manager + CFO). Managers can also modify amounts before approving (partial approval), letting them adjust a $3,000 request down to $2,500 without rejecting it entirely. All actions execute through Auth0 Token Vault — the agent never touches Stripe credentials directly.",
            "scenarios": [
                {
                    "title": "Office supplies — $75 (auto-approve)",
                    "description": "Small office purchase. Below $500 threshold, auto-approved.",
                    "connection": "stripe-prod", "action": "charge",
                    "params": {"type": "expense", "amount_usd": 75, "category": "office_supplies", "description": "Printer paper and pens", "customer": "employee@company.com"},
                    "flow": flow(("agent", "Expense Agent", "Submit $75"), ("platform", "Rule Engine", "No rule match"), ("action", "Auto-Approved", "Token Vault")),
                    "badge": "success", "badgeLabel": "AUTO",
                },
                {
                    "title": "Team dinner — $800 (manager approval)",
                    "description": "Team event expense. $500-$5000 range requires manager approval.",
                    "connection": "stripe-prod", "action": "charge",
                    "params": {"type": "expense", "amount_usd": 800, "category": "team_event", "description": "Team celebration dinner — Q1 targets met", "customer": "employee@company.com"},
                    "flow": flow(("agent", "Expense Agent", "Submit $800"), ("platform", "Rule Engine", "any_one"), ("approver", "Manager", "CIBA push"), ("action", "Approved", "Token Vault")),
                    "badge": "info", "badgeLabel": "MANAGER",
                },
                {
                    "title": "New laptop — $2,400 (manager approval)",
                    "description": "Equipment purchase. Manager approves, can adjust amount (partial approval).",
                    "connection": "stripe-prod", "action": "charge",
                    "params": {"type": "expense", "amount_usd": 2400, "category": "equipment", "description": "MacBook Pro 16-inch for development", "customer": "employee@company.com"},
                    "flow": flow(("agent", "Expense Agent", "Submit $2,400"), ("platform", "Rule Engine", "any_one + partial"), ("approver", "Manager", "May reduce amount"), ("action", "Approved", "Token Vault")),
                    "badge": "info", "badgeLabel": "PARTIAL",
                },
                {
                    "title": "Conference trip — $8,500 (CFO step-up)",
                    "description": "Above $5,000 threshold. Escalates to Manager + CFO dual approval.",
                    "connection": "stripe-prod", "action": "charge",
                    "params": {"type": "expense", "amount_usd": 8500, "category": "travel", "description": "AWS re:Invent 2026 — flights, hotel, registration", "customer": "employee@company.com"},
                    "flow": flow(("agent", "Expense Agent", "Submit $8,500"), ("platform", "Rule Engine", "all_of_n"), ("approver", "Manager", "CIBA push"), ("approver", "CFO", "CIBA push"), ("action", "Approved", "Token Vault")),
                    "badge": "warning", "badgeLabel": "STEP-UP",
                },
            ],
            "setupInfo": [
                {"type": "connection", "name": "stripe-prod", "detail": "Stripe for expense processing"},
                {"type": "connection", "name": "slack-prod", "detail": "Slack for notifications"},
                {"type": "approver", "name": "Manager", "detail": "Approves $500-$5000 expenses"},
                {"type": "approver", "name": "CFO", "detail": "Approves $5000+ expenses"},
                {"type": "rule", "name": "[Expense] Medium", "detail": "$500-$4999 → manager"},
                {"type": "rule", "name": "[Expense] Large", "detail": "$5000+ → manager + CFO"},
            ],
        },

        # ──────────────────────────────────────────────────────────────────────
        # 2. RELEASE MANAGER AGENT
        # ──────────────────────────────────────────────────────────────────────
        {
            "id": "release_manager",
            "title": "Release Manager Agent",
            "icon": "Server",
            "category": "devops",
            "categoryLabel": "DevOps & Software",
            "description": "CI/CD automation agent that manages the full deployment lifecycle. Engineers describe what needs shipping — and the agent handles the rest. Staging deploys go through automatically. Production releases require a maintainer to approve via Guardian push notification before any code reaches live servers. For critical incidents, the agent can deploy emergency hotfixes with a 2-minute approval window from the on-call engineer. Production rollbacks also require lead engineer approval with the same urgency timeout. Every deployment action flows through Auth0 Token Vault, ensuring the agent never holds GitHub deploy keys directly. The approval chain guarantees no code reaches production without human sign-off.",
            "scenarios": [
                {
                    "title": "Deploy to staging (auto-approve)",
                    "description": "Staging deployment. No rule match, auto-approved.",
                    "connection": "github-main", "action": "deploy",
                    "params": {"ref": "main", "environment": "staging", "service": "api"},
                    "flow": flow(("agent", "Release Manager", "Deploy main"), ("platform", "Rule Engine", "No match"), ("action", "Auto-Deploy", "Staging")),
                    "badge": "success", "badgeLabel": "AUTO",
                },
                {
                    "title": "Deploy v2.5.0 to production",
                    "description": "Production deployment requires maintainer approval via Guardian push.",
                    "connection": "github-main", "action": "deploy",
                    "params": {"ref": "v2.5.0", "environment": "production", "service": "api"},
                    "flow": flow(("agent", "Release Manager", "Deploy v2.5.0"), ("platform", "Rule Engine", "any_one"), ("approver", "Maintainer", "CIBA push"), ("action", "Deploy", "Production")),
                    "badge": "info", "badgeLabel": "APPROVAL",
                },
                {
                    "title": "Emergency hotfix (2-min timeout)",
                    "description": "Critical production fix. On-call engineer has 2 minutes to approve.",
                    "connection": "github-main", "action": "deploy",
                    "params": {"ref": "hotfix/payment-crash", "environment": "production", "service": "api", "type": "hotfix"},
                    "flow": flow(("agent", "Release Manager", "Hotfix deploy"), ("platform", "Rule Engine", "specific, 2min"), ("approver", "On-Call", "Urgent CIBA"), ("action", "Deploy", "Production")),
                    "badge": "danger", "badgeLabel": "HOTFIX",
                },
                {
                    "title": "Rollback production to v2.4.8",
                    "description": "Production rollback. Lead engineer approval with 2-minute timeout.",
                    "connection": "github-main", "action": "rollback",
                    "params": {"env": "production", "version": "v2.4.8", "reason": "P0 latency spike after v2.5.0 deploy"},
                    "flow": flow(("agent", "Release Manager", "Rollback"), ("platform", "Rule Engine", "specific, 2min"), ("approver", "Lead Engineer", "Urgent CIBA"), ("action", "Rollback", "v2.4.8")),
                    "badge": "danger", "badgeLabel": "ROLLBACK",
                },
            ],
            "setupInfo": [
                {"type": "connection", "name": "github-main", "detail": "GitHub for deployments"},
                {"type": "connection", "name": "slack-prod", "detail": "Slack for deploy notifications"},
                {"type": "approver", "name": "Maintainer", "detail": "Approves production deploys"},
                {"type": "approver", "name": "Lead Engineer", "detail": "Approves rollbacks"},
                {"type": "approver", "name": "On-Call Engineer", "detail": "Approves hotfixes"},
                {"type": "rule", "name": "[Release] Production deploy", "detail": "Production → maintainer"},
                {"type": "rule", "name": "[Release] Rollback", "detail": "Rollback → lead engineer"},
            ],
        },

        # ──────────────────────────────────────────────────────────────────────
        # 3. SECURITY INCIDENT AGENT
        # ──────────────────────────────────────────────────────────────────────
        {
            "id": "security_incident",
            "title": "Security Incident Agent",
            "icon": "Shield",
            "category": "devops",
            "categoryLabel": "DevOps & Software",
            "description": "Real-time security incident response agent that acts decisively when threats are detected. When the team reports suspicious activity — unusual API traffic, compromised accounts, unauthorized code commits — the agent immediately triages the situation and takes appropriate action. Low-severity alerts are logged to Slack automatically. Medium threats trigger repository locks pending Security Lead approval. For confirmed breaches, the agent can initiate a full production token revocation, which requires both CTO and Security Lead to approve via Guardian push — a nuclear option that ensures no single person can shut down production access alone. Every second counts in incident response, and the agent acts first while keeping humans in the approval loop for critical decisions.",
            "scenarios": [
                {
                    "title": "Log security alert (auto)",
                    "description": "Post alert to #security channel. Auto-approved.",
                    "connection": "slack-prod", "action": "send_message",
                    "params": {"channel": "#security", "message": "[MEDIUM] Multiple failed SSH login attempts from IP 203.0.113.42 — 47 attempts in 5 minutes"},
                    "flow": flow(("agent", "Security Agent", "Alert"), ("platform", "Rule Engine", "No high-risk match"), ("action", "Posted", "#security")),
                    "badge": "success", "badgeLabel": "AUTO",
                },
                {
                    "title": "Lock repository (security lead)",
                    "description": "Lock a repo to prevent unauthorized changes. Security Lead approval.",
                    "connection": "github-prod", "action": "lock_repo",
                    "params": {"repo": "acme/api", "reason": "Suspicious commits detected from compromised account"},
                    "flow": flow(("agent", "Security Agent", "Lock repo"), ("platform", "Rule Engine", "specific"), ("approver", "Security Lead", "CIBA push"), ("action", "Locked", "acme/api")),
                    "badge": "warning", "badgeLabel": "SEC LEAD",
                },
                {
                    "title": "Revoke ALL production tokens (CTO + Security)",
                    "description": "Nuclear option. Revoke all production access. CTO and Security Lead must both approve.",
                    "connection": "github-prod", "action": "revoke_tokens",
                    "params": {"scope": "production", "reason": "Confirmed data breach — all production credentials potentially compromised"},
                    "flow": flow(("agent", "Security Agent", "Revoke all"), ("platform", "Rule Engine", "all_of_n"), ("approver", "CTO", "CIBA push"), ("approver", "Security Lead", "CIBA push"), ("action", "Revoked", "All tokens")),
                    "badge": "danger", "badgeLabel": "CRITICAL",
                },
            ],
            "setupInfo": [
                {"type": "connection", "name": "github-prod", "detail": "GitHub for repo management"},
                {"type": "connection", "name": "slack-prod", "detail": "Slack for alerts"},
                {"type": "approver", "name": "Security Lead", "detail": "Approves repo locks"},
                {"type": "approver", "name": "CTO", "detail": "Co-approves token revocation"},
                {"type": "rule", "name": "[Security] Lock repo", "detail": "Lock → security lead"},
                {"type": "rule", "name": "[Security] Revoke tokens", "detail": "Revoke → CTO + security lead"},
            ],
        },

        # ──────────────────────────────────────────────────────────────────────
        # 4. ACCOUNT TAKEOVER RESPONSE AGENT
        # ──────────────────────────────────────────────────────────────────────
        {
            "id": "account_takeover",
            "title": "Account Takeover Response Agent",
            "icon": "Lock",
            "category": "customer_service",
            "categoryLabel": "Customer Service",
            "description": "Customer account protection agent that handles the full incident lifecycle when accounts are compromised. When customer service receives a report of unauthorized access — suspicious purchases, password changes, or credential stuffing attacks — the agent immediately freezes the affected account (Security Lead approval), notifies the customer, investigates the scope, and issues compensation credits. Small goodwill credits under $100 auto-approve. Larger compensation requires CS Manager sign-off. For confirmed attackers, the agent initiates a permanent ban requiring both Security Lead and Legal to approve — ensuring bans have proper legal backing. The agent prioritizes in order: stop the bleeding (freeze), inform the victim (notify), make it right (compensate).",
            "scenarios": [
                {
                    "title": "Freeze compromised account",
                    "description": "Immediately freeze a suspicious account. Security team approval.",
                    "connection": "salesforce-prod", "action": "update_case",
                    "params": {"type": "account_freeze", "email": "victim@example.com", "reason": "Unauthorized purchases detected — 3 transactions in 2 minutes from new IP"},
                    "flow": flow(("agent", "ATO Agent", "Freeze"), ("platform", "Rule Engine", "specific"), ("approver", "Security Lead", "CIBA push"), ("action", "Frozen", "Account")),
                    "badge": "warning", "badgeLabel": "FREEZE",
                },
                {
                    "title": "Permanent ban (Security + Legal)",
                    "description": "Ban a confirmed attacker. Requires Security Lead + Legal dual approval.",
                    "connection": "salesforce-prod", "action": "update_case",
                    "params": {"type": "permanent_ban", "email": "attacker@malicious.com", "reason": "Confirmed credential stuffing attack", "evidence": "47 failed attempts, 3 successful unauthorized accesses, IP matches known botnet"},
                    "flow": flow(("agent", "ATO Agent", "Ban"), ("platform", "Rule Engine", "all_of_n"), ("approver", "Security Lead", "CIBA push"), ("approver", "Legal", "CIBA push"), ("action", "Banned", "Permanent")),
                    "badge": "danger", "badgeLabel": "BAN",
                },
                {
                    "title": "Compensation credit $150 (CS Manager)",
                    "description": "Issue compensation to affected customer. CS Manager approval for $100+.",
                    "connection": "stripe-prod", "action": "credit",
                    "params": {"amount_usd": 150, "customer": "victim@example.com", "reason": "Account compromise — unauthorized charges reversed + goodwill credit"},
                    "flow": flow(("agent", "ATO Agent", "Credit $150"), ("platform", "Rule Engine", "specific"), ("approver", "CS Manager", "CIBA push"), ("action", "Credited", "$150")),
                    "badge": "info", "badgeLabel": "CREDIT",
                },
            ],
            "setupInfo": [
                {"type": "connection", "name": "salesforce-prod", "detail": "Salesforce for case management"},
                {"type": "connection", "name": "stripe-prod", "detail": "Stripe for compensation"},
                {"type": "connection", "name": "gmail-prod", "detail": "Gmail for security notifications"},
                {"type": "connection", "name": "slack-prod", "detail": "Slack for alerts"},
                {"type": "approver", "name": "Security Lead", "detail": "Approves account freezes + bans"},
                {"type": "approver", "name": "Legal", "detail": "Co-approves permanent bans"},
                {"type": "approver", "name": "CS Manager", "detail": "Approves compensation $100+"},
                {"type": "rule", "name": "[ATO] Freeze account", "detail": "Freeze → security lead"},
                {"type": "rule", "name": "[ATO] Permanent ban", "detail": "Ban → security + legal"},
                {"type": "rule", "name": "[ATO] Compensation credit", "detail": "$100+ → CS manager"},
            ],
        },

        # ──────────────────────────────────────────────────────────────────────
        # 5. RECRUITMENT AGENT
        # ──────────────────────────────────────────────────────────────────────
        {
            "id": "recruitment",
            "title": "Recruitment Agent",
            "icon": "UserPlus",
            "category": "hr",
            "categoryLabel": "Human Resources",
            "description": "Full-lifecycle recruitment agent that handles everything from first interview to onboarding. When hiring managers make decisions — scheduling interviews, extending offers, onboarding new hires — the agent executes the paperwork autonomously. Interview invitations auto-send without approval. Offer letters require HR Manager sign-off via Guardian push. Salary packages above $180K trigger a step-up requiring both HR Manager and CFO approval, preventing unauthorized high-compensation commitments. Termination notices require the most stringent control: both HR Manager and CEO must approve before any termination letter is sent. The agent also handles GitHub organization access — adding new hires as members (IT Manager approval) or admins (IT Manager + CTO dual approval). All emails flow through Gmail via Token Vault, ensuring the agent never holds email credentials.",
            "scenarios": [
                {
                    "title": "Interview invite (auto-approve)",
                    "description": "Send interview scheduling email. No rule match, auto-approved.",
                    "connection": "gmail-prod", "action": "send_email",
                    "params": {"recipient": "candidate@example.com", "subject": "Interview — Senior Engineer", "type": "invite", "body_preview": "We'd like to invite you for a technical interview on Thursday at 2pm."},
                    "flow": flow(("agent", "HR Agent", "Send invite"), ("platform", "Rule Engine", "No match"), ("action", "Sent", "Email")),
                    "badge": "success", "badgeLabel": "AUTO",
                },
                {
                    "title": "Offer letter — $160K (HR Manager)",
                    "description": "Standard offer letter. HR Manager approval required.",
                    "connection": "gmail-prod", "action": "send_email",
                    "params": {"recipient": "candidate@example.com", "subject": "Offer Letter — Senior Engineer, $160,000", "type": "offer_letter", "salary_usd": 160000, "body_preview": "We are pleased to offer you the position of Senior Engineer."},
                    "flow": flow(("agent", "HR Agent", "Send offer"), ("platform", "Rule Engine", "specific"), ("approver", "HR Manager", "CIBA push"), ("action", "Sent", "Offer letter")),
                    "badge": "info", "badgeLabel": "HR",
                },
                {
                    "title": "High salary — $210K (HR + CFO)",
                    "description": "Salary $180K+ triggers dual approval: HR Manager + CFO.",
                    "connection": "gmail-prod", "action": "send_email",
                    "params": {"recipient": "senior@example.com", "subject": "Offer Letter — Staff Engineer, $210,000", "type": "offer_letter", "salary_usd": 210000, "body_preview": "We are pleased to offer you the Staff Engineer position."},
                    "flow": flow(("agent", "HR Agent", "Send offer"), ("platform", "Rule Engine", "all_of_n"), ("approver", "HR Manager", "CIBA push"), ("approver", "CFO", "CIBA push"), ("action", "Sent", "Offer")),
                    "badge": "warning", "badgeLabel": "STEP-UP",
                },
                {
                    "title": "Termination notice (HR + CEO)",
                    "description": "Termination requires HR Manager + CEO dual approval.",
                    "connection": "gmail-prod", "action": "send_email",
                    "params": {"recipient": "employee@company.com", "subject": "Employment Termination Notice", "type": "termination", "body_preview": "We regret to inform you that your employment is terminated."},
                    "flow": flow(("agent", "HR Agent", "Termination"), ("platform", "Rule Engine", "all_of_n"), ("approver", "HR Manager", "CIBA push"), ("approver", "CEO", "CIBA push"), ("action", "Sent", "Notice")),
                    "badge": "danger", "badgeLabel": "CRITICAL",
                },
                {
                    "title": "Add to GitHub org (IT Manager)",
                    "description": "Add new hire to GitHub. IT Manager approval.",
                    "connection": "github-prod", "action": "add_member",
                    "params": {"username": "newhire", "org": "acme-corp", "role": "member"},
                    "flow": flow(("agent", "HR Agent", "Add member"), ("platform", "Rule Engine", "specific"), ("approver", "IT Manager", "CIBA push"), ("action", "Added", "GitHub")),
                    "badge": "info", "badgeLabel": "IT",
                },
            ],
            "setupInfo": [
                {"type": "connection", "name": "gmail-prod", "detail": "Gmail for HR emails"},
                {"type": "connection", "name": "github-prod", "detail": "GitHub for org management"},
                {"type": "connection", "name": "slack-prod", "detail": "Slack for HR announcements"},
                {"type": "approver", "name": "HR Manager", "detail": "Approves offer letters"},
                {"type": "approver", "name": "CFO", "detail": "Co-approves $180k+ salaries"},
                {"type": "approver", "name": "CEO", "detail": "Co-approves terminations"},
                {"type": "approver", "name": "IT Manager", "detail": "Approves GitHub access"},
                {"type": "rule", "name": "[HR] Offer letter", "detail": "Offer → HR manager"},
                {"type": "rule", "name": "[HR] Termination notice", "detail": "Termination → HR + CEO"},
                {"type": "rule", "name": "[HR] GitHub add member", "detail": "Member → IT manager"},
            ],
        },

        # ──────────────────────────────────────────────────────────────────────
        # 6. ACCESS PROVISIONING AGENT
        # ──────────────────────────────────────────────────────────────────────
        {
            "id": "access_provisioning",
            "title": "Access Provisioning Agent",
            "icon": "Key",
            "category": "hr",
            "categoryLabel": "Human Resources",
            "description": "Zero-trust access provisioning agent that enforces least-privilege principles across all systems. When employees join, change roles, or leave — the agent handles every permission change. Standard access (GitHub member) requires IT Manager approval. Admin privileges escalate to CTO approval, preventing unauthorized privilege escalation. Financial system access triggers the highest bar: both CFO and CTO must approve, ensuring no single person can grant access to billing and payment systems. For offboarding, the agent immediately revokes all access across every connected system with HR Manager confirmation — no access lingers after an employee's last day. All permission changes flow through Auth0 Token Vault and are logged in the audit trail.",
            "scenarios": [
                {
                    "title": "Standard access (IT Manager)",
                    "description": "Grant standard GitHub membership. IT Manager approval.",
                    "connection": "github-prod", "action": "add_member",
                    "params": {"username": "jsmith", "org": "acme-corp", "role": "member", "system": "github"},
                    "flow": flow(("agent", "Access Agent", "Grant"), ("platform", "Rule Engine", "specific"), ("approver", "IT Manager", "CIBA push"), ("action", "Granted", "Standard")),
                    "badge": "info", "badgeLabel": "IT",
                },
                {
                    "title": "Admin privileges (CTO)",
                    "description": "Grant admin access. CTO approval required.",
                    "connection": "github-prod", "action": "add_member",
                    "params": {"username": "seniordev", "org": "acme-corp", "role": "admin", "system": "github"},
                    "flow": flow(("agent", "Access Agent", "Grant admin"), ("platform", "Rule Engine", "specific"), ("approver", "CTO", "CIBA push"), ("action", "Granted", "Admin")),
                    "badge": "warning", "badgeLabel": "CTO",
                },
                {
                    "title": "Financial system (CFO + CTO)",
                    "description": "Financial system access requires CFO + CTO dual approval.",
                    "connection": "github-prod", "action": "add_member",
                    "params": {"username": "accountant", "org": "acme-corp", "role": "member", "system": "financial"},
                    "flow": flow(("agent", "Access Agent", "Grant finance"), ("platform", "Rule Engine", "all_of_n"), ("approver", "CFO", "CIBA push"), ("approver", "CTO", "CIBA push"), ("action", "Granted", "Financial")),
                    "badge": "danger", "badgeLabel": "STEP-UP",
                },
                {
                    "title": "Offboarding revoke all",
                    "description": "Revoke all access for departing employee. HR Manager quick approval.",
                    "connection": "github-prod", "action": "remove_member",
                    "params": {"username": "departing", "org": "acme-corp", "reason": "offboarding"},
                    "flow": flow(("agent", "Access Agent", "Revoke all"), ("platform", "Rule Engine", "any_one"), ("approver", "HR Manager", "CIBA push"), ("action", "Revoked", "All systems")),
                    "badge": "info", "badgeLabel": "OFFBOARD",
                },
            ],
            "setupInfo": [
                {"type": "connection", "name": "github-prod", "detail": "GitHub for access management"},
                {"type": "connection", "name": "slack-prod", "detail": "Slack for access notifications"},
                {"type": "approver", "name": "IT Manager", "detail": "Approves standard access"},
                {"type": "approver", "name": "CTO", "detail": "Approves admin access"},
                {"type": "approver", "name": "CFO", "detail": "Co-approves financial access"},
                {"type": "rule", "name": "[Access] Standard access", "detail": "Standard → IT manager"},
                {"type": "rule", "name": "[Access] Admin privileges", "detail": "Admin → CTO"},
                {"type": "rule", "name": "[Access] Financial system", "detail": "Finance → CFO + CTO"},
            ],
        },

        # ──────────────────────────────────────────────────────────────────────
        # 7. PATIENT DATA SHARING AGENT
        # ──────────────────────────────────────────────────────────────────────
        {
            "id": "patient_data",
            "title": "Patient Data Sharing Agent",
            "icon": "Heart",
            "category": "healthcare",
            "categoryLabel": "Healthcare & Clinical",
            "description": "HIPAA-compliant patient data sharing agent that ensures medical records are only shared with proper authorization. When a patient's own treating doctor requests records, sharing auto-approves — no friction for routine care. External clinic referrals require the treating doctor's explicit approval via Guardian push. Insurance company requests trigger the highest individual bar: both the patient's consent (via Patient Representative) and the treating doctor must approve, ensuring patients maintain control over their data. Research data sharing requires Ethics Board review plus Chief Doctor approval — anonymized data only. Every share is logged in a full audit trail with patient ID, recipient, purpose, and data scope. The agent never accesses records directly — Google Drive sharing executes through Token Vault.",
            "scenarios": [
                {
                    "title": "Share with own doctor (auto)",
                    "description": "Share records with patient's own doctor. Auto-approved.",
                    "connection": "google-drive-prod", "action": "share",
                    "params": {"patient_id": "P-1234", "recipient_type": "own_doctor", "recipient_name": "Dr. Smith", "purpose": "Regular checkup follow-up", "data_scope": "full_record"},
                    "flow": flow(("agent", "Data Agent", "Share"), ("platform", "Rule Engine", "No match"), ("action", "Shared", "Dr. Smith")),
                    "badge": "success", "badgeLabel": "AUTO",
                },
                {
                    "title": "External clinic referral (doctor approval)",
                    "description": "Share with different clinic. Treating doctor must approve.",
                    "connection": "google-drive-prod", "action": "share",
                    "params": {"patient_id": "P-1234", "recipient_type": "external_clinic", "recipient_name": "City General Hospital", "purpose": "Cardiology referral", "data_scope": "specific_test"},
                    "flow": flow(("agent", "Data Agent", "Share"), ("platform", "Rule Engine", "specific"), ("approver", "Doctor", "CIBA push"), ("action", "Shared", "External clinic")),
                    "badge": "info", "badgeLabel": "DOCTOR",
                },
                {
                    "title": "Insurance request (patient + doctor)",
                    "description": "Insurance data request. Requires patient consent + doctor approval.",
                    "connection": "google-drive-prod", "action": "share",
                    "params": {"patient_id": "P-1234", "recipient_type": "insurance", "recipient_name": "BlueCross Insurance", "purpose": "Claim verification", "data_scope": "summary"},
                    "flow": flow(("agent", "Data Agent", "Share"), ("platform", "Rule Engine", "all_of_n"), ("approver", "Patient Rep", "Consent"), ("approver", "Doctor", "CIBA push"), ("action", "Shared", "Insurance")),
                    "badge": "warning", "badgeLabel": "CONSENT",
                },
                {
                    "title": "Research study (Ethics + Chief Doctor)",
                    "description": "Share anonymized data for research. Ethics Board + Chief Doctor both approve.",
                    "connection": "google-drive-prod", "action": "share",
                    "params": {"patient_id": "P-1234", "recipient_type": "research", "recipient_name": "Stanford Medical Research", "purpose": "Longitudinal cardiac study", "data_scope": "anonymized"},
                    "flow": flow(("agent", "Data Agent", "Share"), ("platform", "Rule Engine", "all_of_n"), ("approver", "Ethics Board", "Review"), ("approver", "Chief Doctor", "CIBA push"), ("action", "Shared", "Anonymized")),
                    "badge": "danger", "badgeLabel": "ETHICS",
                },
            ],
            "setupInfo": [
                {"type": "connection", "name": "google-drive-prod", "detail": "Google Drive for record sharing"},
                {"type": "connection", "name": "gmail-prod", "detail": "Gmail for data sharing notifications"},
                {"type": "connection", "name": "slack-prod", "detail": "Slack for internal alerts"},
                {"type": "approver", "name": "Doctor", "detail": "Approves external sharing"},
                {"type": "approver", "name": "Patient Rep", "detail": "Patient consent"},
                {"type": "approver", "name": "Ethics Board", "detail": "Approves research sharing"},
                {"type": "approver", "name": "Chief Doctor", "detail": "Co-approves research"},
                {"type": "rule", "name": "[Patient] Share with external", "detail": "External → doctor"},
                {"type": "rule", "name": "[Patient] Share with insurance", "detail": "Insurance → patient + doctor"},
                {"type": "rule", "name": "[Patient] Share for research", "detail": "Research → ethics + chief doctor"},
            ],
        },

        # ──────────────────────────────────────────────────────────────────────
        # 8. PRESCRIPTION REFILL AGENT
        # ──────────────────────────────────────────────────────────────────────
        {
            "id": "prescription_refill",
            "title": "Prescription Refill Agent",
            "icon": "Pill",
            "category": "healthcare",
            "categoryLabel": "Healthcare & Clinical",
            "description": "Pharmacy automation agent that processes prescription refills with built-in safety controls. Routine medications (blood pressure, cholesterol) refill automatically — no delay for standard maintenance drugs. Controlled substances (Schedule II-V: Adderall, Xanax, opioids) require the prescribing doctor's explicit approval via Guardian push before dispensing, preventing unauthorized refills of addictive medications. Dosage changes trigger the strictest review: both the doctor and pharmacist must approve sequentially, ensuring clinical validation and drug interaction checks. New prescriptions also require doctor approval. Every refill action is logged with patient ID, medication, dosage, and approval chain for DEA compliance. The agent flags potential issues but never dispenses without proper authorization.",
            "scenarios": [
                {
                    "title": "Routine refill — Lisinopril (auto)",
                    "description": "Standard medication refill. Auto-approved.",
                    "connection": "gmail-prod", "action": "send_email",
                    "params": {"type": "routine_refill", "patient_id": "P-5678", "medication": "Lisinopril", "dosage": "10mg", "recipient": "pharmacy@clinic.com", "subject": "Rx Refill: Lisinopril 10mg"},
                    "flow": flow(("agent", "Rx Agent", "Refill"), ("platform", "Rule Engine", "No match"), ("action", "Processed", "Pharmacy")),
                    "badge": "success", "badgeLabel": "AUTO",
                },
                {
                    "title": "Controlled substance — Adderall (doctor)",
                    "description": "Schedule II drug. Doctor must approve the refill.",
                    "connection": "gmail-prod", "action": "send_email",
                    "params": {"type": "controlled_refill", "patient_id": "P-9012", "medication": "Adderall", "dosage": "20mg", "recipient": "pharmacy@clinic.com", "subject": "Rx Refill: Adderall 20mg"},
                    "flow": flow(("agent", "Rx Agent", "Refill"), ("platform", "Rule Engine", "specific"), ("approver", "Doctor", "CIBA push"), ("action", "Approved", "Pharmacy")),
                    "badge": "warning", "badgeLabel": "CONTROLLED",
                },
                {
                    "title": "Dosage change — Metformin (doctor + pharmacist)",
                    "description": "Dosage modification. Doctor approves first, then pharmacist verifies.",
                    "connection": "gmail-prod", "action": "send_email",
                    "params": {"type": "dosage_change", "patient_id": "P-3456", "medication": "Metformin", "dosage": "1000mg", "recipient": "pharmacy@clinic.com", "subject": "Rx Dosage Change: Metformin 500mg → 1000mg"},
                    "flow": flow(("agent", "Rx Agent", "Dosage change"), ("platform", "Rule Engine", "all_of_n"), ("approver", "Doctor", "CIBA push"), ("approver", "Pharmacist", "CIBA push"), ("action", "Updated", "Pharmacy")),
                    "badge": "danger", "badgeLabel": "SEQUENTIAL",
                },
                {
                    "title": "New prescription — Amoxicillin (doctor)",
                    "description": "New prescription requires doctor approval before dispensing.",
                    "connection": "gmail-prod", "action": "send_email",
                    "params": {"type": "new_prescription", "patient_id": "P-7890", "medication": "Amoxicillin", "dosage": "500mg", "recipient": "pharmacy@clinic.com", "subject": "New Rx: Amoxicillin 500mg"},
                    "flow": flow(("agent", "Rx Agent", "New Rx"), ("platform", "Rule Engine", "specific"), ("approver", "Doctor", "CIBA push"), ("action", "Prescribed", "Pharmacy")),
                    "badge": "info", "badgeLabel": "DOCTOR",
                },
            ],
            "setupInfo": [
                {"type": "connection", "name": "gmail-prod", "detail": "Gmail for pharmacy notifications"},
                {"type": "connection", "name": "slack-prod", "detail": "Slack for pharmacy notifications"},
                {"type": "approver", "name": "Doctor", "detail": "Approves controlled substances + new Rx"},
                {"type": "approver", "name": "Pharmacist", "detail": "Verifies dosage changes"},
                {"type": "rule", "name": "[Rx] Controlled substance", "detail": "Controlled → doctor"},
                {"type": "rule", "name": "[Rx] Dosage change", "detail": "Dosage → doctor + pharmacist"},
                {"type": "rule", "name": "[Rx] New prescription", "detail": "New Rx → doctor"},
            ],
        },

        # ──────────────────────────────────────────────────────────────────────
        # 9. GDPR REQUEST AGENT
        # ──────────────────────────────────────────────────────────────────────
        {
            "id": "gdpr_request",
            "title": "GDPR Request Agent",
            "icon": "ShieldCheck",
            "category": "legal",
            "categoryLabel": "Legal & Compliance",
            "description": "GDPR and CCPA compliance agent that handles data subject requests within the mandatory 30-day deadline. When users exercise their right to be forgotten, the agent processes deletion requests across all connected systems. Single-user deletions require Privacy Officer approval to verify identity and scope. Bulk deletions (10+ users, common after acquisitions or data cleanup) escalate to CTO + Privacy Officer dual approval — preventing accidental mass data loss. Cross-border data transfers (EU to US, EU to UK) require both Legal and Privacy Officer approval to ensure proper legal basis (adequacy decision, standard contractual clauses, or explicit consent). The agent tracks every request with timestamps, regulatory deadlines, and deletion confirmations for audit compliance.",
            "scenarios": [
                {
                    "title": "Log data request (auto)",
                    "description": "Record incoming GDPR request. Auto-processed for audit trail.",
                    "connection": "slack-prod", "action": "send_message",
                    "params": {"channel": "#privacy", "message": "New GDPR request: user@example.com — Right to Access (Art. 15)"},
                    "flow": flow(("agent", "GDPR Agent", "Log"), ("platform", "Rule Engine", "No match"), ("action", "Logged", "#privacy")),
                    "badge": "success", "badgeLabel": "AUTO",
                },
                {
                    "title": "Delete user data (Privacy Officer)",
                    "description": "Right to be Forgotten. Privacy Officer must approve deletion.",
                    "connection": "github-prod", "action": "deploy",
                    "params": {"type": "gdpr_deletion", "env": "production", "subject_email": "user@example.com", "scope": "full", "is_bulk": False, "migration_name": "delete_user_data_user"},
                    "flow": flow(("agent", "GDPR Agent", "Delete"), ("platform", "Rule Engine", "specific"), ("approver", "Privacy Officer", "CIBA push"), ("action", "Deleted", "14 systems")),
                    "badge": "info", "badgeLabel": "PRIVACY",
                },
                {
                    "title": "Bulk deletion — 25 users (CTO + Privacy)",
                    "description": "Bulk deletion of 10+ users. CTO + Privacy Officer dual approval.",
                    "connection": "github-prod", "action": "deploy",
                    "params": {"type": "gdpr_deletion", "env": "production", "subject_email": "batch-25-inactive@company.com", "scope": "full", "is_bulk": True, "migration_name": "bulk_delete_25_users"},
                    "flow": flow(("agent", "GDPR Agent", "Bulk delete"), ("platform", "Rule Engine", "all_of_n"), ("approver", "CTO", "CIBA push"), ("approver", "Privacy Officer", "CIBA push"), ("action", "Deleted", "25 users")),
                    "badge": "warning", "badgeLabel": "STEP-UP",
                },
                {
                    "title": "Cross-border transfer to US (Legal + Privacy)",
                    "description": "Transfer EU data to US. Legal + Privacy Officer must both approve.",
                    "connection": "gmail-prod", "action": "send_email",
                    "params": {"type": "cross_border_transfer", "recipient": "dpo@analytics-us.com", "subject": "Data Transfer Agreement — EU to US", "destination": "United States", "legal_basis": "adequacy_decision"},
                    "flow": flow(("agent", "GDPR Agent", "Transfer"), ("platform", "Rule Engine", "all_of_n"), ("approver", "Legal", "Review"), ("approver", "Privacy Officer", "CIBA push"), ("action", "Transferred", "EU→US")),
                    "badge": "danger", "badgeLabel": "CROSS-BORDER",
                },
            ],
            "setupInfo": [
                {"type": "connection", "name": "github-prod", "detail": "GitHub for deletion scripts"},
                {"type": "connection", "name": "gmail-prod", "detail": "Gmail for compliance emails"},
                {"type": "connection", "name": "slack-prod", "detail": "Slack for privacy alerts"},
                {"type": "approver", "name": "Privacy Officer", "detail": "Approves deletions + transfers"},
                {"type": "approver", "name": "CTO", "detail": "Co-approves bulk deletions"},
                {"type": "approver", "name": "Legal", "detail": "Co-approves cross-border transfers"},
                {"type": "rule", "name": "[GDPR] Single user deletion", "detail": "Delete → privacy officer"},
                {"type": "rule", "name": "[GDPR] Bulk deletion", "detail": "Bulk → CTO + privacy"},
                {"type": "rule", "name": "[GDPR] Cross-border transfer", "detail": "Transfer → legal + privacy"},
            ],
        },

        # ──────────────────────────────────────────────────────────────────────
        # 10. API KEY ROTATION AGENT
        # ──────────────────────────────────────────────────────────────────────
        {
            "id": "api_key_rotation",
            "title": "API Key Rotation Agent",
            "icon": "Zap",
            "category": "devops",
            "categoryLabel": "DevOps & Software",
            "description": "Credential lifecycle agent that ensures API keys and secrets are rotated before they become security risks. Scheduled 90-day rotations auto-execute with zero downtime using a blue-green deployment strategy — no approval needed for routine hygiene. When a key is potentially compromised (found in a public repo, flagged by a security scan), the agent triggers an emergency rotation requiring Security Lead approval with a tight 3-minute window. Third-party API keys (SendGrid, Twilio, payment processors) require CTO approval since they affect vendor relationships. The nuclear option — rotating ALL production keys simultaneously — requires both CTO and Security Lead, ensuring infrastructure-wide credential changes have proper oversight. Auth0 Token Vault is central to this agent's design: rotated credentials are stored in Vault, never exposed to the agent itself.",
            "scenarios": [
                {
                    "title": "Scheduled rotation — Stripe (auto)",
                    "description": "Regular 90-day rotation. Auto-approved.",
                    "connection": "github-prod", "action": "deploy",
                    "params": {"type": "key_rotation", "env": "production", "service": "stripe", "urgency": "scheduled", "reason": "90-day rotation policy", "is_third_party": False, "migration_name": "rotate_stripe_key"},
                    "flow": flow(("agent", "Key Agent", "Rotate"), ("platform", "Rule Engine", "No match"), ("action", "Rotated", "Stripe key")),
                    "badge": "success", "badgeLabel": "AUTO",
                },
                {
                    "title": "Emergency rotation — GitHub token (Security Lead)",
                    "description": "Potentially compromised key. Security Lead approval, 3-min timeout.",
                    "connection": "github-prod", "action": "deploy",
                    "params": {"type": "key_rotation", "env": "production", "service": "github", "urgency": "emergency", "reason": "Token found in public gist — potential exposure", "is_third_party": False, "migration_name": "rotate_github_key"},
                    "flow": flow(("agent", "Key Agent", "Emergency"), ("platform", "Rule Engine", "specific"), ("approver", "Security Lead", "Urgent CIBA"), ("action", "Rotated", "GitHub token")),
                    "badge": "warning", "badgeLabel": "EMERGENCY",
                },
                {
                    "title": "Third-party key — SendGrid (CTO)",
                    "description": "Third-party API key rotation. CTO approval required.",
                    "connection": "github-prod", "action": "deploy",
                    "params": {"type": "key_rotation", "env": "production", "service": "sendgrid", "urgency": "scheduled", "reason": "Vendor security advisory — rotate recommended", "is_third_party": True, "migration_name": "rotate_sendgrid_key"},
                    "flow": flow(("agent", "Key Agent", "3rd party"), ("platform", "Rule Engine", "specific"), ("approver", "CTO", "CIBA push"), ("action", "Rotated", "SendGrid key")),
                    "badge": "info", "badgeLabel": "CTO",
                },
                {
                    "title": "Full rotation — ALL keys (CTO + Security)",
                    "description": "Nuclear option: rotate every production key. CTO + Security Lead.",
                    "connection": "github-prod", "action": "deploy",
                    "params": {"type": "key_rotation", "env": "production", "scope": "production", "urgency": "emergency", "reason": "Infrastructure breach — rotating all credentials", "migration_name": "rotate_all_keys"},
                    "flow": flow(("agent", "Key Agent", "Rotate ALL"), ("platform", "Rule Engine", "all_of_n"), ("approver", "CTO", "CIBA push"), ("approver", "Security Lead", "CIBA push"), ("action", "Rotated", "All keys")),
                    "badge": "danger", "badgeLabel": "CRITICAL",
                },
            ],
            "setupInfo": [
                {"type": "connection", "name": "github-prod", "detail": "GitHub for rotation scripts"},
                {"type": "connection", "name": "slack-prod", "detail": "Slack for rotation alerts"},
                {"type": "connection", "name": "gmail-prod", "detail": "Gmail for rotation reports"},
                {"type": "approver", "name": "Security Lead", "detail": "Approves emergency rotations"},
                {"type": "approver", "name": "CTO", "detail": "Approves third-party + full rotations"},
                {"type": "rule", "name": "[KeyRotation] Emergency rotation", "detail": "Emergency → security lead"},
                {"type": "rule", "name": "[KeyRotation] Third-party key", "detail": "3rd party → CTO"},
                {"type": "rule", "name": "[KeyRotation] Full rotation", "detail": "All keys → CTO + security"},
            ],
        },

        # ──────────────────────────────────────────────────────────────────────
        # 11. FINANCE AGENT
        # ──────────────────────────────────────────────────────────────────────
        {
            "id": "finance",
            "title": "Finance Operations Agent",
            "icon": "Banknote",
            "category": "finance",
            "categoryLabel": "Commerce & Finance",
            "description": "Autonomous payment processing agent that handles invoices, vendor payments, and financial transfers. Small payments under $500 auto-approve. $500-$5,000 requires manager sign-off. Above $5,000 needs CFO approval. The agent enforces a $10,000 daily budget — once exceeded, all further payments are blocked until the next day. When processing bulk vendor payments, the agent adapts by trying individual payments to stay within budget limits. All transactions flow through Auth0 Token Vault, keeping Stripe and PayPal credentials server-side.",
            "scenarios": [
                {
                    "title": "Small invoice — $200 (auto-approve)",
                    "description": "Small vendor payment. Under $500, auto-approved.",
                    "connection": "stripe-prod", "action": "charge",
                    "params": {"amount_usd": 200, "customer": "Acme Corp", "description": "Office supplies invoice #1234", "method": "stripe"},
                    "flow": flow(("agent", "Finance Agent", "Pay $200"), ("platform", "Rule Engine", "No match"), ("action", "Auto-Paid", "Token Vault")),
                    "badge": "success", "badgeLabel": "AUTO",
                },
                {
                    "title": "Design agency — $5,000 (CFO approval)",
                    "description": "Large transfer. $5,000+ requires CFO approval.",
                    "connection": "stripe-prod", "action": "charge",
                    "params": {"amount_usd": 5000, "customer": "Creative Agency", "description": "Q1 branding project — overdue", "method": "stripe"},
                    "flow": flow(("agent", "Finance Agent", "Pay $5,000"), ("platform", "Rule Engine", "specific"), ("approver", "CFO", "CIBA push"), ("action", "Approved", "Token Vault")),
                    "badge": "warning", "badgeLabel": "CFO",
                },
                {
                    "title": "Bulk vendors — $50,000 (budget block)",
                    "description": "15 pending vendors totaling $50,000. Daily budget ($10,000) exceeded — BLOCKED.",
                    "connection": "stripe-prod", "action": "charge",
                    "params": {"amount_usd": 50000, "customer": "Multiple Vendors", "description": "Bulk vendor payment — 15 pending invoices"},
                    "flow": flow(("agent", "Finance Agent", "Pay $50,000"), ("platform", "Rule Engine", "Budget check"), ("gate", "BLOCKED", "Daily limit exceeded")),
                    "badge": "danger", "badgeLabel": "BLOCKED",
                },
            ],
            "setupInfo": [
                {"type": "connection", "name": "stripe-prod", "detail": "Stripe for payments"},
                {"type": "connection", "name": "gmail-prod", "detail": "Gmail for invoices"},
                {"type": "approver", "name": "Manager", "detail": "Approves $500-$5000"},
                {"type": "approver", "name": "CFO", "detail": "Approves $5000+"},
                {"type": "rule", "name": "[Finance] Medium", "detail": "$500-$4999 → manager"},
                {"type": "rule", "name": "[Finance] Large", "detail": "$5000+ → CFO"},
            ],
        },

        # ──────────────────────────────────────────────────────────────────────
        # 12. TRAVELOPS AGENT
        # ──────────────────────────────────────────────────────────────────────
        {
            "id": "travelops",
            "title": "Travel Operations Agent",
            "icon": "Plane",
            "category": "finance",
            "categoryLabel": "Commerce & Finance",
            "description": "Corporate travel booking agent that handles flights, hotels, and ground transportation. Economy flights under $500 auto-approve. $500-$2,000 needs manager approval, $2,000-$5,000 needs VP, and $5,000+ escalates to CFO. Business/first class always requires VP regardless of price. Hotel suites need CFO. The agent calculates team travel totals and cascades multiple approvals for luxury bookings. Credentials for Stripe and booking APIs are isolated in Auth0 Token Vault.",
            "scenarios": [
                {
                    "title": "Budget flight — $200 (auto-approve)",
                    "description": "Economy flight under $500. Auto-approved.",
                    "connection": "stripe-prod", "action": "charge",
                    "params": {"amount_usd": 200, "customer": "Alice Johnson", "description": "Flight Berlin → London (economy)", "type": "travel_flight", "cabin_class": "economy"},
                    "flow": flow(("agent", "Travel Agent", "Book $200"), ("platform", "Rule Engine", "No match"), ("action", "Booked", "Token Vault")),
                    "badge": "success", "badgeLabel": "AUTO",
                },
                {
                    "title": "Team business class — $9,000 (CFO)",
                    "description": "3 business class tickets at $3,000 each. Total $9,000 → CFO approval.",
                    "connection": "stripe-prod", "action": "charge",
                    "params": {"amount_usd": 9000, "customer": "Engineering Team", "description": "Flight SFO → LHR x3 (business)", "type": "travel_flight", "cabin_class": "business"},
                    "flow": flow(("agent", "Travel Agent", "Book $9,000"), ("platform", "Rule Engine", "specific"), ("approver", "CFO", "CIBA push"), ("action", "Booked", "Token Vault")),
                    "badge": "warning", "badgeLabel": "CFO",
                },
                {
                    "title": "Executive luxury — $15,000+ (cascading)",
                    "description": "First class + Ritz suite + car service. Multiple step-ups cascade.",
                    "connection": "stripe-prod", "action": "charge",
                    "params": {"amount_usd": 15000, "customer": "VP Operations", "description": "Flight NYC → TYO (first class)", "type": "travel_flight", "cabin_class": "first"},
                    "flow": flow(("agent", "Travel Agent", "Book $15,000"), ("platform", "Rule Engine", "specific"), ("approver", "CFO", "CIBA push"), ("gate", "Multiple bookings", "Hotel + transport"), ("action", "Cascade", "3 approvals")),
                    "badge": "danger", "badgeLabel": "CASCADE",
                },
            ],
            "setupInfo": [
                {"type": "connection", "name": "stripe-prod", "detail": "Stripe for bookings"},
                {"type": "approver", "name": "Manager", "detail": "Approves $500-$2000 flights"},
                {"type": "approver", "name": "VP Operations", "detail": "Approves business/first class"},
                {"type": "approver", "name": "CFO", "detail": "Approves $5000+ and suites"},
                {"type": "rule", "name": "[Travel] Flights", "detail": "Tiered by amount + class"},
                {"type": "rule", "name": "[Travel] Hotel suite", "detail": "Suite → CFO"},
            ],
        },

        # ──────────────────────────────────────────────────────────────────────
        # 13. OPEN SOURCE AGENT
        # ──────────────────────────────────────────────────────────────────────
        {
            "id": "opensource",
            "title": "Open Source Maintenance Agent",
            "icon": "GitBranch",
            "category": "devops",
            "categoryLabel": "DevOps & Software",
            "description": "Community-driven project maintenance agent. Bug fix PRs merge automatically. Feature PRs require 2-of-3 maintainer votes (k-of-n quorum). Releases need the same 2-of-3 approval. npm publishing — the highest supply chain risk — requires ALL maintainers to approve (all-of-n). Bounty payments under $200 auto-approve, larger bounties need CFO sign-off. This agent demonstrates supply chain protection: even if the agent is compromised, it cannot publish to npm without unanimous maintainer consent.",
            "scenarios": [
                {
                    "title": "Typo fix PR #42 (auto-merge)",
                    "description": "Bug fix PR. Auto-approved and merged.",
                    "connection": "github-prod", "action": "merge_pr",
                    "params": {"repo": "acme/sdk", "pr_number": 42, "type": "bugfix"},
                    "flow": flow(("agent", "OSS Agent", "Merge PR"), ("platform", "Rule Engine", "No match"), ("action", "Merged", "GitHub")),
                    "badge": "success", "badgeLabel": "AUTO",
                },
                {
                    "title": "v2.0 release (2-of-3 maintainers)",
                    "description": "New release. 2-of-3 maintainer quorum required.",
                    "connection": "github-prod", "action": "deploy",
                    "params": {"type": "release", "env": "production", "ref": "v2.0.0", "notes": "Major release with new auth module", "publish_npm": False},
                    "flow": flow(("agent", "OSS Agent", "Create release"), ("platform", "Rule Engine", "k_of_n (2/3)"), ("approver", "Maintainer 1", "Vote"), ("approver", "Maintainer 2", "Vote"), ("action", "Released", "GitHub")),
                    "badge": "info", "badgeLabel": "QUORUM",
                },
                {
                    "title": "npm publish + $5,000 bounties (ALL + CFO)",
                    "description": "Publish to npm needs ALL maintainers. Bounties need CFO.",
                    "connection": "github-prod", "action": "deploy",
                    "params": {"type": "release", "env": "production", "ref": "v2.0.0", "notes": "Publish to npm registry", "publish_npm": True},
                    "flow": flow(("agent", "OSS Agent", "Publish npm"), ("platform", "Rule Engine", "all_of_n"), ("approver", "All 3 Maintainers", "Must agree"), ("gate", "Supply Chain", "Maximum protection"), ("action", "Published", "npm")),
                    "badge": "danger", "badgeLabel": "ALL MUST APPROVE",
                },
            ],
            "setupInfo": [
                {"type": "connection", "name": "github-prod", "detail": "GitHub for PRs and releases"},
                {"type": "connection", "name": "stripe-prod", "detail": "Stripe for bounty payments"},
                {"type": "approver", "name": "Maintainer", "detail": "Project maintainer #1"},
                {"type": "approver", "name": "Maintainer 2", "detail": "Project maintainer #2"},
                {"type": "approver", "name": "Maintainer 3", "detail": "Project maintainer #3"},
                {"type": "rule", "name": "[OSS] Feature PR", "detail": "2-of-3 maintainer quorum"},
                {"type": "rule", "name": "[OSS] npm publish", "detail": "ALL maintainers required"},
            ],
        },

        # ──────────────────────────────────────────────────────────────────────
        # 14. RESEARCH AGENT
        # ──────────────────────────────────────────────────────────────────────
        {
            "id": "research",
            "title": "Research Operations Agent",
            "icon": "FlaskConical",
            "category": "finance",
            "categoryLabel": "Commerce & Finance",
            "description": "Lab operations agent managing GPU clusters, paper submissions, and dataset acquisitions. Paper submissions auto-approve (no financial risk). Compute under $500 auto-approves. $500-$5,000 needs Principal Investigator (PI) approval. Over $5,000 requires PI + Department Head. Dataset purchases follow a similar tier. The $10,000 daily compute budget prevents runaway cloud costs — when a researcher requests a 64-GPU H100 cluster for a week ($50,000+), it gets blocked immediately.",
            "scenarios": [
                {
                    "title": "Paper submission — NeurIPS (auto)",
                    "description": "Research paper submission. No financial impact, auto-approved.",
                    "connection": "gmail-prod", "action": "send_email",
                    "params": {"recipient": "submissions@neurips.org", "subject": "Paper Submission: Attention Is All You Need v2", "type": "paper_submission"},
                    "flow": flow(("agent", "Research Agent", "Submit paper"), ("platform", "Rule Engine", "No match"), ("action", "Submitted", "Email sent")),
                    "badge": "success", "badgeLabel": "AUTO",
                },
                {
                    "title": "4x A100 cluster — $1,200 (PI approval)",
                    "description": "Medium compute request. PI approval required.",
                    "connection": "stripe-prod", "action": "charge",
                    "params": {"amount_usd": 1200, "customer": "lab-transformer-v2", "description": "4x A100 for 24h", "type": "compute"},
                    "flow": flow(("agent", "Research Agent", "Provision $1,200"), ("platform", "Rule Engine", "specific"), ("approver", "PI", "CIBA push"), ("action", "Provisioned", "GPU cluster")),
                    "badge": "info", "badgeLabel": "PI",
                },
                {
                    "title": "64x H100 cluster — $50,000 (blocked)",
                    "description": "Massive compute request. Exceeds daily budget — BLOCKED.",
                    "connection": "stripe-prod", "action": "charge",
                    "params": {"amount_usd": 50000, "customer": "lab-foundation-model", "description": "64x H100 for 168h", "type": "compute"},
                    "flow": flow(("agent", "Research Agent", "Provision $50K"), ("platform", "Rule Engine", "all_of_n"), ("approver", "PI + Dept Head", "Both required"), ("gate", "BLOCKED", "Budget exceeded")),
                    "badge": "danger", "badgeLabel": "BLOCKED",
                },
            ],
            "setupInfo": [
                {"type": "connection", "name": "stripe-prod", "detail": "Stripe for compute and datasets"},
                {"type": "connection", "name": "gmail-prod", "detail": "Gmail for submissions"},
                {"type": "approver", "name": "Principal Investigator", "detail": "Approves $500-$5000 compute"},
                {"type": "approver", "name": "Department Head", "detail": "Co-approves $5000+ compute"},
                {"type": "rule", "name": "[Research] Compute", "detail": "Tiered by cost"},
                {"type": "rule", "name": "[Research] Dataset", "detail": "$1000+ needs PI + CFO"},
            ],
        },

        # ──────────────────────────────────────────────────────────────────────
        # 15. COMMS AGENT
        # ──────────────────────────────────────────────────────────────────────
        {
            "id": "comms",
            "title": "Communications Agent",
            "icon": "MessageSquare",
            "category": "hr",
            "categoryLabel": "Corporate & HR",
            "description": "Multi-channel communications agent handling Slack, email, and Discord. Internal Slack messages auto-approve. External emails to clients require manager approval. Mass emails to 10+ recipients need CEO + Manager approval. Press releases need CEO + Legal. The scope creep detection catches when an agent tries to email thousands of people — a critical safeguard against accidental mass communications that could damage the company's reputation.",
            "scenarios": [
                {
                    "title": "Sprint review reminder — Slack (auto)",
                    "description": "Internal Slack message. Auto-approved.",
                    "connection": "slack-prod", "action": "send_message",
                    "params": {"channel": "#engineering", "message": "Sprint review at 3pm today in the main conf room"},
                    "flow": flow(("agent", "Comms Agent", "Send Slack"), ("platform", "Rule Engine", "No match"), ("action", "Sent", "Slack")),
                    "badge": "success", "badgeLabel": "AUTO",
                },
                {
                    "title": "Client email — Q1 update (manager)",
                    "description": "External email to client. Manager approval required.",
                    "connection": "gmail-prod", "action": "send_email",
                    "params": {"recipient": "contact@bigcorp.com", "subject": "Q1 Project Update — Results & Next Steps", "type": "external", "recipient_count": 1},
                    "flow": flow(("agent", "Comms Agent", "Send email"), ("platform", "Rule Engine", "any_one"), ("approver", "Manager", "CIBA push"), ("action", "Sent", "Gmail")),
                    "badge": "info", "badgeLabel": "MANAGER",
                },
                {
                    "title": "Newsletter to 10,000 — mass block",
                    "description": "Mass email to 10,000 subscribers. Scope creep — CEO + Manager required.",
                    "connection": "gmail-prod", "action": "send_email",
                    "params": {"recipient": "newsletter@company.com", "subject": "Press Release: New Product Launch", "type": "external", "recipient_count": 10000},
                    "flow": flow(("agent", "Comms Agent", "Mass email"), ("platform", "Rule Engine", "all_of_n"), ("approver", "Manager", "CIBA push"), ("approver", "CEO", "CIBA push"), ("gate", "Scope Creep", "10,000 recipients")),
                    "badge": "danger", "badgeLabel": "SCOPE CREEP",
                },
            ],
            "setupInfo": [
                {"type": "connection", "name": "slack-prod", "detail": "Slack for messages"},
                {"type": "connection", "name": "gmail-prod", "detail": "Gmail for emails"},
                {"type": "approver", "name": "Manager", "detail": "Approves external emails"},
                {"type": "approver", "name": "CEO", "detail": "Co-approves mass emails"},
                {"type": "rule", "name": "[Comms] External email", "detail": "External → manager"},
                {"type": "rule", "name": "[Comms] Mass email", "detail": "10+ recipients → manager + CEO"},
            ],
        },
    ]


# ── Seed Endpoint ─────────────────────────────────────────────────────────────

@router.post("/seed")
async def seed_demo_data(
    request: Request,
    agent_id: str | None = None,
    real_user_id: str | None = None,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Idempotently create demo connections, approvers, and rules.
    If agent_id is provided, only creates resources needed by that agent."""
    created = {"connections": 0, "approvers": 0, "rules": 0, "skipped": 0}

    # Map agent_id → needed connections and approver roles
    _AGENT_DEPS = {
        "expense": {"conns": ["stripe-prod", "slack-prod"], "roles": ["manager", "cfo"]},
        "release_manager": {"conns": ["github-main", "slack-prod"], "roles": ["maintainer", "lead_engineer", "oncall_engineer"]},
        "security_incident": {"conns": ["github-prod", "slack-prod"], "roles": ["security_lead", "cto"]},
        "account_takeover": {"conns": ["salesforce-prod", "stripe-prod", "gmail-prod", "slack-prod"], "roles": ["security_lead", "legal", "cs_manager"]},
        "recruitment": {"conns": ["gmail-prod", "github-prod", "slack-prod"], "roles": ["hr_manager", "cfo", "ceo", "it_manager", "cto"]},
        "access_provisioning": {"conns": ["github-prod", "slack-prod"], "roles": ["it_manager", "cto", "cfo", "hr_manager"]},
        "patient_data": {"conns": ["google-drive-prod", "gmail-prod", "slack-prod"], "roles": ["doctor", "patient_rep", "ethics_board", "chief_doctor"]},
        "prescription_refill": {"conns": ["gmail-prod", "slack-prod"], "roles": ["doctor", "pharmacist"]},
        "gdpr_request": {"conns": ["github-prod", "gmail-prod", "slack-prod"], "roles": ["privacy_officer", "cto", "legal"]},
        "api_key_rotation": {"conns": ["github-prod", "slack-prod", "gmail-prod"], "roles": ["security_lead", "cto"]},
        "finance": {"conns": ["stripe-prod", "gmail-prod", "slack-prod"], "roles": ["manager", "cfo"]},
        "travelops": {"conns": ["stripe-prod", "gmail-prod", "slack-prod"], "roles": ["manager", "vp", "cfo"]},
        "opensource": {"conns": ["github-prod", "stripe-prod", "slack-prod"], "roles": ["maintainer", "maintainer2", "maintainer3", "cfo", "cto"]},
        "research": {"conns": ["stripe-prod", "gmail-prod", "slack-prod"], "roles": ["pi", "dept_head", "cfo"]},
        "comms": {"conns": ["slack-prod", "gmail-prod"], "roles": ["manager", "ceo"]},
    }

    needed_conns = None
    needed_roles = None
    if agent_id and agent_id in _AGENT_DEPS:
        needed_conns = set(_AGENT_DEPS[agent_id]["conns"])
        needed_roles = set(_AGENT_DEPS[agent_id]["roles"])

    # ── Connections ───────────────────────────────────────────────────────
    existing_conns = {}
    result = await db.execute(
        select(ServiceConnection).where(ServiceConnection.workspace_id == workspace.id)
    )
    for c in result.scalars().all():
        existing_conns[c.slug] = c.id

    for conn_def in CONNECTIONS:
        if needed_conns and conn_def["slug"] not in needed_conns:
            continue
        if conn_def["slug"] in existing_conns:
            created["skipped"] += 1
            continue
        conn = ServiceConnection(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            name=conn_def["name"],
            service=conn_def["service"],
            slug=conn_def["slug"],
            actions=conn_def["actions"],
            token_vault_connection_id=conn_def.get("tv_id", conn_def["service"]),
            config_meta=conn_def.get("config_meta"),
        )
        db.add(conn)
        existing_conns[conn_def["slug"]] = conn.id
        created["connections"] += 1

    # ── Approvers ────────────────────────────────────────────────────────
    existing_approvers = {}
    result = await db.execute(
        select(Approver).where(Approver.workspace_id == workspace.id)
    )
    for a in result.scalars().all():
        existing_approvers[a.auth0_user_id] = a.id

    # Use real user's Auth0 ID for all approvers so CIBA Guardian push works
    # In demo mode, all approvers map to the logged-in user's phone
    effective_user_id = real_user_id or workspace.owner_auth0_sub or ""

    approver_role_map: dict[str, uuid.UUID] = {}
    for approver_def in APPROVERS:
        auth0_id = effective_user_id if effective_user_id else approver_def["auth0_user_id"]
        role = approver_def["role"]

        if needed_roles and role not in needed_roles:
            if auth0_id in existing_approvers:
                approver_role_map[role] = existing_approvers[auth0_id]
            continue

        # Skip if approver with same name already exists in this workspace
        existing_by_name = None
        result_check = await db.execute(
            select(Approver).where(
                Approver.workspace_id == workspace.id,
                Approver.name == approver_def["name"],
            ).limit(1)
        )
        existing_approver = result_check.scalar_one_or_none()
        if existing_approver:
            approver_role_map[role] = existing_approver.id
            created["skipped"] += 1
            continue

        approver = Approver(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            name=approver_def["name"],
            email=approver_def["email"],
            auth0_user_id=auth0_id,
            notify_channel=["guardian_push"],
            urgent_channel=["guardian_push"],
        )
        db.add(approver)
        approver_role_map[role] = approver.id
        existing_approvers[auth0_id] = approver.id
        created["approvers"] += 1

    await db.flush()

    # ── Rules ────────────────────────────────────────────────────────────
    # Map agent_id → rule name prefixes for filtering
    _AGENT_RULE_PREFIXES = {
        "expense": ["[Expense]"],
        "release_manager": ["[Release]"],
        "security_incident": ["[Security]", "[Shared]"],
        "account_takeover": ["[ATO]"],
        "recruitment": ["[HR]"],
        "access_provisioning": ["[Access]"],
        "patient_data": ["[Patient]"],
        "prescription_refill": ["[Rx]"],
        "gdpr_request": ["[GDPR]"],
        "api_key_rotation": ["[KeyRotation]"],
        "finance": ["[Finance]"],
        "travelops": ["[Travel]"],
        "opensource": ["[OSS]"],
        "research": ["[Research]"],
        "comms": ["[Comms]"],
    }

    existing_rules = set()
    result = await db.execute(
        select(Rule.name).where(Rule.workspace_id == workspace.id)
    )
    for row in result.scalars().all():
        existing_rules.add(row)

    # Filter rules by agent_id if specified
    allowed_prefixes = None
    if agent_id and agent_id in _AGENT_RULE_PREFIXES:
        allowed_prefixes = _AGENT_RULE_PREFIXES[agent_id]

    for rule_def in _build_rules(approver_role_map):
        if rule_def["name"] in existing_rules:
            created["skipped"] += 1
            continue

        # Skip rules not belonging to the requested agent
        if allowed_prefixes and not any(rule_def["name"].startswith(p) for p in allowed_prefixes):
            continue

        approver_roles = rule_def.pop("approver_roles", [])
        partial = rule_def.pop("partial_approval", False)
        k_val = rule_def.pop("k_value", None)

        rule = Rule(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            name=rule_def["name"],
            connection=rule_def["connection"],
            action=rule_def["action"],
            model=rule_def["model"],
            conditions=rule_def.get("conditions", []),
            timeout_seconds=rule_def.get("timeout_seconds", 300),
            context_template=rule_def.get("context_template"),
            partial_approval=partial,
            k_value=k_val,
            is_active=True,
            priority=rule_def.get("priority", 0),
        )
        db.add(rule)

        for i, role in enumerate(approver_roles):
            approver_id = approver_role_map.get(role)
            if approver_id:
                db.add(RuleApprover(
                    id=uuid.uuid4(),
                    rule_id=rule.id,
                    approver_id=approver_id,
                    order=i,
                ))

        created["rules"] += 1

    await db.commit()
    return {"status": "ok", **created}


@router.get("/agents")
async def get_demo_agents(
    _ws: Workspace = Depends(get_current_workspace),
):
    """Return the 10 demo agent catalog. Requires authenticated workspace."""
    return _build_agent_catalog()


class DeleteRequest(BaseModel):
    agent_id: str | None = None
    rule_ids: list[str] | None = None
    approver_ids: list[str] | None = None
    connection_ids: list[str] | None = None


@router.post("/delete")
async def clear_demo_data(
    body: DeleteRequest,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Remove specific demo resources by ID. If IDs not given, delete all for agent."""
    agent_id = body.agent_id
    # If IDs list is provided (even empty), only delete those specific IDs
    # If IDs list is None (field not sent), delete all matching
    delete_rules = body.rule_ids is None
    delete_approvers = body.approver_ids is None
    delete_connections = body.connection_ids is None

    _AGENT_RULE_PREFIXES = {
        "expense": ["[Expense]"],
        "release_manager": ["[Release]"],
        "security_incident": ["[Security]", "[Shared]"],
        "account_takeover": ["[ATO]"],
        "recruitment": ["[HR]"],
        "access_provisioning": ["[Access]"],
        "patient_data": ["[Patient]"],
        "prescription_refill": ["[Rx]"],
        "gdpr_request": ["[GDPR]"],
        "api_key_rotation": ["[KeyRotation]"],
        "finance": ["[Finance]"],
        "travelops": ["[Travel]"],
        "opensource": ["[OSS]"],
        "research": ["[Research]"],
        "comms": ["[Comms]"],
    }

    _AGENT_DEPS = {
        "expense": {"conns": ["stripe-prod", "slack-prod"], "roles": ["manager", "cfo"]},
        "release_manager": {"conns": ["github-main", "slack-prod"], "roles": ["maintainer", "lead_engineer", "oncall_engineer"]},
        "security_incident": {"conns": ["github-prod", "slack-prod"], "roles": ["security_lead", "cto"]},
        "account_takeover": {"conns": ["salesforce-prod", "stripe-prod", "gmail-prod", "slack-prod"], "roles": ["security_lead", "legal", "cs_manager"]},
        "recruitment": {"conns": ["gmail-prod", "github-prod", "slack-prod"], "roles": ["hr_manager", "cfo", "ceo", "it_manager", "cto"]},
        "access_provisioning": {"conns": ["github-prod", "slack-prod"], "roles": ["it_manager", "cto", "cfo", "hr_manager"]},
        "patient_data": {"conns": ["google-drive-prod", "gmail-prod", "slack-prod"], "roles": ["doctor", "patient_rep", "ethics_board", "chief_doctor"]},
        "prescription_refill": {"conns": ["gmail-prod", "slack-prod"], "roles": ["doctor", "pharmacist"]},
        "gdpr_request": {"conns": ["github-prod", "gmail-prod", "slack-prod"], "roles": ["privacy_officer", "cto", "legal"]},
        "api_key_rotation": {"conns": ["github-prod", "slack-prod", "gmail-prod"], "roles": ["security_lead", "cto"]},
        "finance": {"conns": ["stripe-prod", "gmail-prod", "slack-prod"], "roles": ["manager", "cfo"]},
        "travelops": {"conns": ["stripe-prod", "gmail-prod", "slack-prod"], "roles": ["manager", "vp", "cfo"]},
        "opensource": {"conns": ["github-prod", "stripe-prod", "slack-prod"], "roles": ["maintainer", "maintainer2", "maintainer3", "cfo", "cto"]},
        "research": {"conns": ["stripe-prod", "gmail-prod", "slack-prod"], "roles": ["pi", "dept_head", "cfo"]},
        "comms": {"conns": ["slack-prod", "gmail-prod"], "roles": ["manager", "ceo"]},
    }

    if agent_id and agent_id in _AGENT_RULE_PREFIXES:
        demo_prefixes = tuple(_AGENT_RULE_PREFIXES[agent_id])
        target_conns = set(_AGENT_DEPS[agent_id]["conns"])
        target_roles = set(_AGENT_DEPS[agent_id]["roles"])
    else:
        demo_prefixes = ("[Expense]", "[Release]", "[Security]", "[ATO]", "[HR]", "[Access]",
                         "[Patient]", "[Rx]", "[GDPR]", "[KeyRotation]", "[Shared]", "[Demo]")
        target_conns = None
        target_roles = None

    # 1. Delete rules + rule_approvers
    deleted_rules = 0
    if body.rule_ids is not None:
        # Delete specific rules by ID
        for rid in body.rule_ids:
            result = await db.execute(select(Rule).where(Rule.id == uuid.UUID(rid), Rule.workspace_id == workspace.id))
            rule = result.scalar_one_or_none()
            if rule:
                ra_result = await db.execute(select(RuleApprover).where(RuleApprover.rule_id == rule.id))
                for ra in ra_result.scalars().all():
                    await db.delete(ra)
                await db.delete(rule)
                deleted_rules += 1
    elif delete_rules:
        # Delete all matching rules
        result = await db.execute(select(Rule).where(Rule.workspace_id == workspace.id))
        for rule in result.scalars().all():
            if any(rule.name.startswith(p) for p in demo_prefixes):
                ra_result = await db.execute(select(RuleApprover).where(RuleApprover.rule_id == rule.id))
                for ra in ra_result.scalars().all():
                    await db.delete(ra)
                await db.delete(rule)
                deleted_rules += 1

    # 2. Delete approvers
    deleted_approvers = 0
    if body.approver_ids is not None:
        for aid in body.approver_ids:
            result = await db.execute(select(Approver).where(Approver.id == uuid.UUID(aid), Approver.workspace_id == workspace.id))
            approver = result.scalar_one_or_none()
            if approver:
                await db.delete(approver)
                deleted_approvers += 1
    elif delete_approvers:
        _role_to_auth0 = {a["role"]: a["auth0_user_id"] for a in APPROVERS}
        result = await db.execute(select(Approver).where(Approver.workspace_id == workspace.id))
        for approver in result.scalars().all():
            if not approver.auth0_user_id or not approver.auth0_user_id.startswith("demo|"):
                continue
            if target_roles is not None:
                approver_role = next((r for r, aid in _role_to_auth0.items() if aid == approver.auth0_user_id), None)
                if approver_role not in target_roles:
                    continue
            await db.delete(approver)
            deleted_approvers += 1

    # 3. Delete connections
    deleted_conns = 0
    if body.connection_ids is not None:
        for cid in body.connection_ids:
            result = await db.execute(select(ServiceConnection).where(ServiceConnection.id == uuid.UUID(cid), ServiceConnection.workspace_id == workspace.id))
            conn = result.scalar_one_or_none()
            if conn:
                await db.delete(conn)
                deleted_conns += 1
    elif delete_connections:
        allowed_slugs = target_conns if target_conns else {c["slug"] for c in CONNECTIONS}
        result = await db.execute(select(ServiceConnection).where(ServiceConnection.workspace_id == workspace.id))
        for conn in result.scalars().all():
            if conn.slug in allowed_slugs:
                await db.delete(conn)
                deleted_conns += 1

    await db.commit()
    return {
        "status": "ok",
        "deleted_rules": deleted_rules,
        "deleted_approvers": deleted_approvers,
        "deleted_connections": deleted_conns,
    }

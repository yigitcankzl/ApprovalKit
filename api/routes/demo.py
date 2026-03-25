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

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.approver import Approver
from api.models.connection import ServiceConnection
from api.models.rule import Rule, RuleApprover, ApprovalModel, TimeoutAction
from api.models.workspace import Workspace

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


@router.post("/seed")
async def seed_demo_data(agent_id: str | None = None, db: AsyncSession = Depends(get_db)):
    """
    Idempotently seed demo data. Pass ?agent_id=ecommerce to seed only
    one agent's data. Without agent_id, seeds everything.
    """
    report: dict[str, list[str]] = {
        "created": [], "skipped": []
    }

    # ── 1. Workspace ──────────────────────────────────────────────────────────
    ws_result = await db.execute(
        select(Workspace).where(Workspace.is_active.is_(True)).limit(1)
    )
    workspace = ws_result.scalar_one_or_none()
    if not workspace:
        workspace = Workspace(name="Demo Workspace", is_active=True)
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
            continue
        uid = appr_def["auth0_user_id"]
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
async def clear_demo_data(db: AsyncSession = Depends(get_db)):
    """Remove all demo resources (names start with '[Demo]')."""
    ws_result = await db.execute(
        select(Workspace).where(Workspace.is_active.is_(True)).limit(1)
    )
    workspace = ws_result.scalar_one_or_none()
    if not workspace:
        return {"status": "ok", "deleted": 0}

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

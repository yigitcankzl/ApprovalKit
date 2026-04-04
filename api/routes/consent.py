"""
Consent & Permissions endpoint
===============================
Aggregated view of what agents can access, connected services,
OAuth scopes, and recent access history.
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.connection import ServiceConnection
from api.models.rule import Rule, ApprovalModel
from api.models.approval_job import ApprovalJob
from api.models.workspace import Workspace
from api.routes.connections import _SERVICE_SCOPE, _DEFAULT_SCOPE
from api.middleware.workspace import get_current_workspace

router = APIRouter(prefix="/api/v1", tags=["consent"])


@router.get("/consent")
async def get_consent(workspace: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    # All active connections for this workspace
    conns_result = await db.execute(
        select(ServiceConnection)
        .where(ServiceConnection.workspace_id == workspace.id, ServiceConnection.is_active.is_(True))
        .order_by(ServiceConnection.name)
    )
    connections = conns_result.scalars().all()

    # All active rules for this workspace
    rules_result = await db.execute(
        select(Rule).where(Rule.workspace_id == workspace.id, Rule.is_active.is_(True))
    )
    all_rules = rules_result.scalars().all()
    rules_by_conn = {}
    for r in all_rules:
        rules_by_conn.setdefault(r.connection, []).append(r)

    # Count distinct agents for this workspace
    agent_count_result = await db.execute(
        select(func.count(distinct(ApprovalJob.agent_user_id)))
        .where(ApprovalJob.workspace_id == workspace.id)
    )
    total_agents = agent_count_result.scalar() or 0

    services = []
    for conn in connections:
        conn_rules = rules_by_conn.get(conn.slug, [])

        jobs_result = await db.execute(
            select(ApprovalJob)
            .where(ApprovalJob.workspace_id == workspace.id, ApprovalJob.connection == conn.slug)
            .order_by(ApprovalJob.created_at.desc())
            .limit(10)
        )
        recent_jobs = jobs_result.scalars().all()

        services.append({
            "connection_id": str(conn.id),
            "name": conn.name,
            "service": conn.service,
            "slug": conn.slug,
            "connected_user": conn.connected_user_name,
            "connected_auth0_user_id": conn.connected_auth0_user_id,
            "oauth_scopes": _SERVICE_SCOPE.get(conn.service.lower(), _DEFAULT_SCOPE),
            "actions": conn.actions or [],
            "rules": [
                {
                    "id": str(r.id),
                    "name": r.name,
                    "model": r.model.value if isinstance(r.model, ApprovalModel) else r.model,
                    "action": r.action,
                    "approver_count": len(r.rule_approvers),
                    "step_up_model": r.step_up_model.value if r.step_up_model and isinstance(r.step_up_model, ApprovalModel) else None,
                }
                for r in conn_rules
            ],
            "recent_access": [
                {
                    "job_id": str(j.id),
                    "agent_user_id": j.agent_user_id,
                    "action": j.action,
                    "state": j.state.value,
                    "created_at": j.created_at.isoformat(),
                }
                for j in recent_jobs
            ],
            "can_revoke": conn.connected_auth0_user_id is not None,
        })

    return {
        "services": services,
        "total_agents": total_agents,
        "total_rules": len(all_rules),
    }


@router.get("/consent/permission-map")
async def get_permission_map(workspace: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    """Build a comprehensive permission map: agents -> connections -> actions -> stats.

    This provides a single view showing what each agent can access,
    which scopes are granted, and how actively each permission is used.
    """
    from api.models.agent import RegisteredAgent
    from datetime import datetime, timedelta

    week_ago = datetime.utcnow() - timedelta(days=7)

    # Get all agents
    agents_result = await db.execute(
        select(RegisteredAgent)
        .where(RegisteredAgent.workspace_id == workspace.id, RegisteredAgent.is_active.is_(True))
        .order_by(RegisteredAgent.created_at.desc())
    )
    agents = agents_result.scalars().all()

    # Get all connections
    conns_result = await db.execute(
        select(ServiceConnection)
        .where(ServiceConnection.workspace_id == workspace.id, ServiceConnection.is_active.is_(True))
    )
    connections = conns_result.scalars().all()
    conn_map = {c.slug: c for c in connections}

    # Get all rules
    rules_result = await db.execute(
        select(Rule).where(Rule.workspace_id == workspace.id, Rule.is_active.is_(True))
    )
    all_rules = rules_result.scalars().all()

    # Get all jobs from last 7 days for usage stats
    jobs_result = await db.execute(
        select(ApprovalJob)
        .where(ApprovalJob.workspace_id == workspace.id, ApprovalJob.created_at >= week_ago)
    )
    recent_jobs = jobs_result.scalars().all()

    # Build usage index: agent -> connection -> {total, approved, rejected, last_used}
    usage_index: dict[str, dict[str, dict]] = {}
    for j in recent_jobs:
        agent_key = j.agent_user_id
        conn_key = j.connection
        if agent_key not in usage_index:
            usage_index[agent_key] = {}
        if conn_key not in usage_index[agent_key]:
            usage_index[agent_key][conn_key] = {"total": 0, "approved": 0, "rejected": 0, "last_used": None, "actions": set()}
        bucket = usage_index[agent_key][conn_key]
        bucket["total"] += 1
        bucket["actions"].add(j.action)
        if j.state.value == "approved" or j.state.value == "pre_approved":
            bucket["approved"] += 1
        elif j.state.value == "rejected":
            bucket["rejected"] += 1
        if not bucket["last_used"] or j.created_at > bucket["last_used"]:
            bucket["last_used"] = j.created_at

    # Build agent permission entries
    agent_permissions = []
    for agent in agents:
        agent_name = agent.name
        allowed = agent.allowed_connections

        permissions = []
        for conn in connections:
            # Check if agent is allowed to use this connection
            if allowed:
                if isinstance(allowed, list) and conn.slug not in allowed:
                    continue
                if isinstance(allowed, dict) and conn.slug not in allowed:
                    continue

            # Get rules governing this connection
            conn_rules = [r for r in all_rules if r.connection == conn.slug]

            # Get usage stats
            agent_usage = usage_index.get(agent_name, {}).get(conn.slug, {})

            scopes = _SERVICE_SCOPE.get(conn.service.lower(), _DEFAULT_SCOPE) if conn.service else _DEFAULT_SCOPE

            permissions.append({
                "connection": conn.slug,
                "service": conn.service,
                "name": conn.name,
                "connected": conn.connected_auth0_user_id is not None,
                "scopes": scopes,
                "actions": conn.actions or [],
                "rules_count": len(conn_rules),
                "models": list(set(
                    r.model.value if isinstance(r.model, ApprovalModel) else r.model
                    for r in conn_rules
                )),
                "usage_7d": {
                    "total": agent_usage.get("total", 0),
                    "approved": agent_usage.get("approved", 0),
                    "rejected": agent_usage.get("rejected", 0),
                    "actions_used": list(agent_usage.get("actions", set())),
                    "last_used": agent_usage["last_used"].isoformat() if agent_usage.get("last_used") else None,
                },
            })

        trust_score = getattr(agent, "trust_score", 100) or 100
        agent_permissions.append({
            "agent_id": str(agent.id),
            "agent_name": agent_name,
            "description": agent.description,
            "trust_score": trust_score,
            "trust_level": "high" if trust_score >= 80 else "medium" if trust_score >= 50 else "low",
            "allowed_connections": allowed,
            "total_connections": len(permissions),
            "permissions": permissions,
        })

    return {
        "agents": agent_permissions,
        "total_agents": len(agents),
        "total_connections": len(connections),
        "total_rules": len(all_rules),
    }

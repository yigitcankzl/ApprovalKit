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
from api.routes.connections import _SERVICE_SCOPE

router = APIRouter(prefix="/api/v1", tags=["consent"])


@router.get("/consent")
async def get_consent(db: AsyncSession = Depends(get_db)):
    # All active connections
    conns_result = await db.execute(
        select(ServiceConnection)
        .where(ServiceConnection.is_active.is_(True))
        .order_by(ServiceConnection.name)
    )
    connections = conns_result.scalars().all()

    # All active rules
    rules_result = await db.execute(
        select(Rule).where(Rule.is_active.is_(True))
    )
    all_rules = rules_result.scalars().all()
    rules_by_conn = {}
    for r in all_rules:
        rules_by_conn.setdefault(r.connection, []).append(r)

    # Count distinct agents
    agent_count_result = await db.execute(
        select(func.count(distinct(ApprovalJob.agent_user_id)))
    )
    total_agents = agent_count_result.scalar() or 0

    services = []
    for conn in connections:
        # Rules for this connection
        conn_rules = rules_by_conn.get(conn.slug, [])

        # Recent access for this connection
        jobs_result = await db.execute(
            select(ApprovalJob)
            .where(ApprovalJob.connection == conn.slug)
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
            "oauth_scopes": _SERVICE_SCOPE.get(conn.service.lower(), "openid profile email"),
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

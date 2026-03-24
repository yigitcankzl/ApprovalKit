import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.approval_job import ApprovalJob, AuditLog, AuditEventType, JobState
from api.models.approver import Approver
from api.schemas.audit import AuditLogResponse, DashboardStats
from api.services.fga import fga_client
from api.middleware.fga import require_audit_read
from api.middleware.rate_limit import rate_limiter

router = APIRouter(prefix="/api/v1", tags=["audit"])


@router.get("/audit")
async def get_audit_log(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    event_type: str | None = None,
    connection: str | None = None,
    _fga: None = Depends(require_audit_read),
):
    query = (
        select(AuditLog)
        .join(ApprovalJob, AuditLog.job_id == ApprovalJob.id)
        .order_by(AuditLog.created_at.desc())
    )

    if event_type:
        query = query.where(AuditLog.event_type == event_type)
    if connection:
        query = query.where(ApprovalJob.connection == connection)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        {
            "id": str(log.id),
            "job_id": str(log.job_id),
            "approver_id": str(log.approver_id) if log.approver_id else None,
            "approver_name": log.approver.name if log.approver else None,
            "event_type": log.event_type.value if isinstance(log.event_type, AuditEventType) else log.event_type,
            "action": log.job.action if log.job else "",
            "connection": log.job.connection if log.job else "",
            "binding_message": log.binding_message,
            "modified_params": log.modified_params,
            "note": log.note,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    week_ago = datetime.utcnow() - timedelta(days=7)

    # Total actions this week
    total_result = await db.execute(
        select(func.count(ApprovalJob.id)).where(ApprovalJob.created_at >= week_ago)
    )
    total = total_result.scalar() or 0

    # Count by state
    async def count_state(state: JobState) -> int:
        result = await db.execute(
            select(func.count(ApprovalJob.id)).where(
                ApprovalJob.created_at >= week_ago,
                ApprovalJob.state == state,
            )
        )
        return result.scalar() or 0

    approved = await count_state(JobState.APPROVED) + await count_state(JobState.PRE_APPROVED)
    rejected = await count_state(JobState.REJECTED)
    blocked = await count_state(JobState.BLOCKED)
    timed_out = await count_state(JobState.TIMEOUT)

    # Active pre-approvals
    pre_result = await db.execute(
        select(func.count()).select_from(
            select(ApprovalJob.id).where(ApprovalJob.state == JobState.PRE_APPROVED).subquery()
        )
    )
    active_pre = pre_result.scalar() or 0

    # Active delegations
    del_result = await db.execute(
        select(func.count(Approver.id)).where(
            Approver.delegate_to.is_not(None),
            Approver.delegate_until >= datetime.utcnow(),
        )
    )
    active_delegations = del_result.scalar() or 0

    # CIBA quota
    ciba_info = await rate_limiter.check_ciba_quota()

    # Scope creep alerts
    scope_result = await db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.event_type == AuditEventType.SCOPE_CREEP,
            AuditLog.created_at >= week_ago,
        )
    )
    scope_creep = scope_result.scalar() or 0

    return DashboardStats(
        total_actions_week=total,
        approved=approved,
        rejected=rejected,
        blocked=blocked,
        timed_out=timed_out,
        active_pre_approvals=active_pre,
        active_delegations=active_delegations,
        ciba_usage=ciba_info["current"],
        ciba_limit=ciba_info["limit"],
        scope_creep_alerts=scope_creep,
    )


@router.get("/ciba-quota")
async def get_ciba_quota():
    return await rate_limiter.check_ciba_quota()


@router.post("/connections/{connection_id}/revoke")
async def revoke_connection(connection_id: str):
    from api.services.token_vault import token_vault_service
    success = await token_vault_service.revoke_connection(connection_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to revoke connection")
    return {"status": "revoked", "connection_id": connection_id}

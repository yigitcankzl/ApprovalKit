import asyncio
import json
import uuid
from datetime import datetime, timedelta

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import get_db
from api.models.approval_job import ApprovalJob, AuditLog, AuditEventType, JobState
from api.models.approver import Approver
from api.schemas.audit import AuditLogResponse, DashboardStats
from api.services.fga import fga_client
from api.middleware.fga import require_audit_read
from api.middleware.rate_limit import rate_limiter
from api.middleware.workspace import get_current_workspace
from api.models.workspace import Workspace

router = APIRouter(prefix="/api/v1", tags=["audit"])
settings = get_settings()


@router.get("/events")
async def stream_events(request: Request):
    """SSE endpoint — streams approval events in real-time via Redis pub/sub."""
    async def generator():
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = r.pubsub()
        await pubsub.subscribe("approval_events")
        try:
            while True:
                if await request.is_disconnected():
                    break
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    yield f"data: {message['data']}\n\n"
                else:
                    yield ": ping\n\n"
                await asyncio.sleep(0.5)
        finally:
            await pubsub.unsubscribe("approval_events")
            await r.aclose()

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


_LIVE_EVENT_TYPES = (
    AuditEventType.REQUESTED,
    AuditEventType.CIBA_SENT,
    AuditEventType.APPROVED,
    AuditEventType.REJECTED,
    AuditEventType.TIMEOUT,
    AuditEventType.BLOCKED,
    AuditEventType.PRE_APPROVED,
    AuditEventType.PARTIAL_APPROVED,
    AuditEventType.STEP_UP,
    AuditEventType.ESCALATED,
)


@router.get("/recent-activity")
async def get_recent_activity(
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, le=50),
):
    result = await db.execute(
        select(AuditLog)
        .join(ApprovalJob, AuditLog.job_id == ApprovalJob.id)
        .where(AuditLog.event_type.in_(_LIVE_EVENT_TYPES))
        .where(ApprovalJob.workspace_id == workspace.id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()

    out = []
    for log in logs:
        job = log.job
        et = log.event_type.value if isinstance(log.event_type, AuditEventType) else log.event_type
        out.append({
            "type": et,
            "job_id": str(log.job_id),
            "connection": job.connection if job else "",
            "action": job.action if job else "",
            "timestamp": log.created_at.isoformat(),
            "note": log.note,
        })
    return out


@router.get("/audit")
async def get_audit_log(
    workspace: Workspace = Depends(get_current_workspace),
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
        .where(ApprovalJob.workspace_id == workspace.id)
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
async def get_dashboard(workspace: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    week_ago = datetime.utcnow() - timedelta(days=7)

    # Total actions this week
    total_result = await db.execute(
        select(func.count(ApprovalJob.id)).where(
            ApprovalJob.workspace_id == workspace.id,
            ApprovalJob.created_at >= week_ago,
        )
    )
    total = total_result.scalar() or 0

    # Count by state
    async def count_state(state: JobState) -> int:
        result = await db.execute(
            select(func.count(ApprovalJob.id)).where(
                ApprovalJob.workspace_id == workspace.id,
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
            select(ApprovalJob.id).where(
                ApprovalJob.workspace_id == workspace.id,
                ApprovalJob.state == JobState.PRE_APPROVED,
            ).subquery()
        )
    )
    active_pre = pre_result.scalar() or 0

    # Active delegations
    del_result = await db.execute(
        select(func.count(Approver.id)).where(
            Approver.workspace_id == workspace.id,
            Approver.delegate_to.is_not(None),
            Approver.delegate_until >= datetime.utcnow(),
        )
    )
    active_delegations = del_result.scalar() or 0

    # CIBA quota
    ciba_info = await rate_limiter.check_ciba_quota()

    # Scope creep alerts
    scope_result = await db.execute(
        select(func.count(AuditLog.id))
        .join(ApprovalJob, AuditLog.job_id == ApprovalJob.id)
        .where(
            ApprovalJob.workspace_id == workspace.id,
            AuditLog.event_type == AuditEventType.SCOPE_CREEP,
            AuditLog.created_at >= week_ago,
        )
    )
    scope_creep = scope_result.scalar() or 0

    # Pending approvals count
    pending_result = await db.execute(
        select(func.count(ApprovalJob.id)).where(
            ApprovalJob.workspace_id == workspace.id,
            ApprovalJob.state.in_([
                JobState.PENDING, JobState.CIBA_SENT,
                JobState.WAITING_APPROVAL, JobState.PARTIALLY_APPROVED,
            ])
        )
    )
    pending_count = pending_result.scalar() or 0

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
        pending_count=pending_count,
    )


@router.get("/ciba-quota")
async def get_ciba_quota():
    return await rate_limiter.check_ciba_quota()


@router.get("/security-status")
async def get_security_status(db: AsyncSession = Depends(get_db)):
    """
    Returns real-time status for each security layer.
    Frontend uses this to replace hardcoded 'Active' badges.
    """
    from api.config import get_settings
    from api.models.workspace import Workspace
    from api.models.connection import ServiceConnection

    settings = get_settings()

    # 1. HMAC — check workspaces have a non-empty hmac_secret
    hmac_ok = False
    hmac_detail = "No workspaces configured"
    try:
        ws_result = await db.execute(
            select(func.count(Workspace.id)).where(
                Workspace.is_active.is_(True),
                Workspace.hmac_secret.is_not(None),
                Workspace.hmac_secret != "",
            )
        )
        ws_count = ws_result.scalar() or 0
        if ws_count > 0:
            hmac_ok = True
            hmac_detail = f"{ws_count} workspace{'s' if ws_count > 1 else ''} secured"
        else:
            hmac_detail = "No workspace has an HMAC secret"
    except Exception as e:
        hmac_detail = f"Error: {e}"

    # 2. FGA — store + API URL both configured
    fga_configured = bool(settings.FGA_API_URL and settings.FGA_STORE_ID)
    fga_ok = fga_configured
    if fga_configured:
        fga_detail = f"Store {settings.FGA_STORE_ID[:8]}… active"
    elif settings.FGA_API_URL or settings.FGA_STORE_ID:
        fga_detail = "Partial config — store or API URL missing"
    else:
        fga_detail = "Not configured (allow-all mode)"

    # 3. Token Vault — connections with stored credentials
    vault_ok = False
    vault_detail = "No connections linked to Auth0 Token Vault"
    try:
        cred_result = await db.execute(
            select(func.count(ServiceConnection.id)).where(
                ServiceConnection.is_active.is_(True),
                ServiceConnection.connected_auth0_user_id.is_not(None),
            )
        )
        cred_count = cred_result.scalar() or 0
        if cred_count > 0:
            vault_ok = True
            vault_detail = f"{cred_count} connection{'s' if cred_count > 1 else ''} via Auth0 Token Vault"
        else:
            vault_detail = "No OAuth connections — connect via /connections"
    except Exception as e:
        vault_detail = f"Error: {e}"

    # 4. Credentials key isolation — is CREDENTIALS_KEY separate from HMAC_SECRET?
    cred_key_ok = bool(settings.CREDENTIALS_KEY)
    cred_key_detail = (
        "Dedicated CREDENTIALS_KEY in use"
        if cred_key_ok
        else "Falling back to HMAC_SECRET — run setup.py"
    )

    # 5. Sentry error tracking
    sentry_ok = bool(settings.SENTRY_DSN)
    sentry_detail = "DSN configured" if sentry_ok else "SENTRY_DSN not set"

    return {
        "hmac": {"ok": hmac_ok, "detail": hmac_detail},
        "fga": {"ok": fga_ok, "detail": fga_detail},
        "token_vault": {"ok": vault_ok, "detail": vault_detail},
        "credentials_key": {"ok": cred_key_ok, "detail": cred_key_detail},
        "sentry": {"ok": sentry_ok, "detail": sentry_detail},
    }


@router.post("/connections/{connection_id}/revoke")
async def revoke_connection(connection_id: str):
    from api.services.token_vault import token_vault_service
    success = await token_vault_service.revoke_connection(connection_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to revoke connection")
    return {"status": "revoked", "connection_id": connection_id}

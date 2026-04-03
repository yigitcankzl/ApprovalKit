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
async def stream_events(request: Request, workspace: Workspace = Depends(get_current_workspace)):
    """SSE endpoint — workspace-scoped real-time approval events."""
    ws_id = str(workspace.id)

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
                    # Filter: only forward events for this workspace
                    try:
                        event = json.loads(message["data"])
                        if event.get("workspace_id", ws_id) == ws_id:
                            yield f"data: {message['data']}\n\n"
                    except (json.JSONDecodeError, KeyError):
                        pass
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
            "risk_score": getattr(log.job, "risk_score", 0) or 0 if log.job else 0,
            "risk_level": getattr(log.job, "risk_level", "low") or "low" if log.job else "low",
            "agent_user_id": log.job.agent_user_id if log.job else None,
        }
        for log in logs
    ]


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard(workspace: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    week_ago = datetime.utcnow() - timedelta(days=7)

    # Single GROUP BY query for all state counts (R2: eliminates N+1)
    state_result = await db.execute(
        select(ApprovalJob.state, func.count(ApprovalJob.id))
        .where(ApprovalJob.workspace_id == workspace.id, ApprovalJob.created_at >= week_ago)
        .group_by(ApprovalJob.state)
    )
    counts = {row[0]: row[1] for row in state_result.all()}

    total = sum(counts.values())
    approved = counts.get(JobState.APPROVED, 0) + counts.get(JobState.PRE_APPROVED, 0)
    rejected = counts.get(JobState.REJECTED, 0)
    blocked = counts.get(JobState.BLOCKED, 0)
    timed_out = counts.get(JobState.TIMEOUT, 0)
    active_pre = counts.get(JobState.PRE_APPROVED, 0)

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

    # Pending from same counts dict (includes non-week jobs too, so separate query)
    pending_count = counts.get(JobState.PENDING, 0) + counts.get(JobState.CIBA_SENT, 0) + counts.get(JobState.WAITING_APPROVAL, 0) + counts.get(JobState.PARTIALLY_APPROVED, 0)

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
async def get_ciba_quota(_ws: Workspace = Depends(get_current_workspace)):
    return await rate_limiter.check_ciba_quota()


@router.get("/security-status")
async def get_security_status(_ws: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
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
async def revoke_connection(connection_id: str, workspace: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    from api.models.connection import ServiceConnection
    result = await db.execute(
        select(ServiceConnection).where(
            ServiceConnection.id == uuid.UUID(connection_id),
            ServiceConnection.workspace_id == workspace.id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found in your workspace")
    from api.services.token_vault import token_vault_service
    success = await token_vault_service.revoke_connection(connection_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to revoke connection")
    return {"status": "revoked", "connection_id": connection_id}


@router.get("/audit/export")
async def export_audit_log(
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    fmt: str = Query(default="json"),
):
    """
    AIUC-1 compliant audit export.
    Returns a structured JSON audit trail suitable for compliance reports.
    Query params: from=ISO8601, to=ISO8601, fmt=json|csv
    """
    from datetime import datetime as dt
    from fastapi.responses import StreamingResponse as SR
    import csv, io

    since = dt.fromisoformat(from_date) if from_date else dt.utcnow() - timedelta(days=90)
    until = dt.fromisoformat(to_date) if to_date else dt.utcnow()

    result = await db.execute(
        select(ApprovalJob)
        .where(
            ApprovalJob.workspace_id == workspace.id,
            ApprovalJob.created_at >= since,
            ApprovalJob.created_at <= until,
        )
        .order_by(ApprovalJob.created_at.asc())
        .limit(5000)
    )
    jobs = result.scalars().all()

    total = len(jobs)
    approved = sum(1 for j in jobs if j.state == JobState.APPROVED)
    rejected = sum(1 for j in jobs if j.state == JobState.REJECTED)
    auto_approved = sum(1 for j in jobs if j.state == JobState.PRE_APPROVED)
    latencies = [
        (j.completed_at - j.created_at).total_seconds()
        for j in jobs
        if j.completed_at and j.created_at and j.state in (JobState.APPROVED, JobState.REJECTED)
    ]
    avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else 0

    events = [
        {
            "timestamp": j.created_at.isoformat(),
            "job_id": str(j.id),
            "agent_id": j.agent_user_id,
            "connection": j.connection,
            "action": j.action,
            "decision": j.state.value,
            "risk_score": getattr(j, "risk_score", 0) or 0,
            "risk_level": getattr(j, "risk_level", "low") or "low",
            "rejection_reason": getattr(j, "rejection_reason", None),
            "params_modified": j.final_params is not None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        }
        for j in jobs
    ]

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(events[0].keys()) if events else [
            "timestamp", "job_id", "agent_id", "connection", "action", "decision",
            "risk_score", "risk_level", "rejection_reason", "params_modified", "completed_at",
        ])
        writer.writeheader()
        writer.writerows(events)
        csv_bytes = output.getvalue().encode()
        return SR(
            iter([csv_bytes]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=approvalkit-audit-{since.date()}-{until.date()}.csv"},
        )

    payload = {
        "aiuc_version": "1.0-draft",
        "export_timestamp": dt.utcnow().isoformat(),
        "export_period": {"from": since.isoformat(), "to": until.isoformat()},
        "workspace_id": str(workspace.id),
        "summary": {
            "total_requests": total,
            "auto_approved": auto_approved,
            "human_approved": approved,
            "rejected": rejected,
            "pending_or_other": total - approved - rejected - auto_approved,
            "average_latency_seconds": avg_latency,
        },
        "events": events,
    }
    return payload


@router.get("/audit/risk-distribution")
async def get_risk_distribution(
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    days: int = Query(default=7, le=365),
):
    """Risk score distribution for dashboard visualization."""
    since = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(ApprovalJob)
        .where(ApprovalJob.workspace_id == workspace.id, ApprovalJob.created_at >= since)
    )
    jobs = result.scalars().all()

    buckets = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    scores = []
    by_connection: dict[str, dict] = {}
    for j in jobs:
        level = getattr(j, "risk_level", "low") or "low"
        score = getattr(j, "risk_score", 0) or 0
        buckets[level] = buckets.get(level, 0) + 1
        scores.append(score)

        conn = j.connection
        if conn not in by_connection:
            by_connection[conn] = {"total": 0, "avg_risk": 0, "max_risk": 0, "scores": []}
        by_connection[conn]["total"] += 1
        by_connection[conn]["scores"].append(score)

    for conn, data in by_connection.items():
        data["avg_risk"] = round(sum(data["scores"]) / len(data["scores"]), 1) if data["scores"] else 0
        data["max_risk"] = max(data["scores"]) if data["scores"] else 0
        del data["scores"]

    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    return {
        "distribution": buckets,
        "total": len(jobs),
        "avg_score": avg_score,
        "by_connection": by_connection,
        "period_days": days,
    }


@router.get("/audit/patterns")
async def get_approval_patterns(
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    days: int = Query(default=30, le=365),
):
    """Analyze approval history and extract patterns (inspired by Claude Code's agent memory)."""
    since = datetime.utcnow() - timedelta(days=days)

    # Get all jobs in period
    result = await db.execute(
        select(ApprovalJob)
        .where(ApprovalJob.workspace_id == workspace.id, ApprovalJob.created_at >= since)
        .order_by(ApprovalJob.created_at.desc())
    )
    jobs = result.scalars().all()

    if not jobs:
        return {"patterns": [], "stats": {"total_jobs": 0, "period_days": days}}

    # Analyze patterns
    patterns = []
    by_connection: dict[str, dict] = {}
    by_action: dict[str, dict] = {}

    for j in jobs:
        key_conn = j.connection
        key_action = f"{j.connection}/{j.action}"

        if key_conn not in by_connection:
            by_connection[key_conn] = {"total": 0, "approved": 0, "rejected": 0, "blocked": 0, "amounts": []}
        by_connection[key_conn]["total"] += 1
        if j.state == JobState.APPROVED: by_connection[key_conn]["approved"] += 1
        elif j.state == JobState.REJECTED: by_connection[key_conn]["rejected"] += 1
        elif j.state == JobState.BLOCKED: by_connection[key_conn]["blocked"] += 1
        amt = j.params.get("amount_usd") or j.params.get("amount")
        if amt: by_connection[key_conn]["amounts"].append(float(amt))

        if key_action not in by_action:
            by_action[key_action] = {"total": 0, "approved": 0, "rejected": 0, "avg_time": []}
        by_action[key_action]["total"] += 1
        if j.state == JobState.APPROVED:
            by_action[key_action]["approved"] += 1
            if j.completed_at and j.created_at:
                by_action[key_action]["avg_time"].append((j.completed_at - j.created_at).total_seconds())
        elif j.state == JobState.REJECTED:
            by_action[key_action]["rejected"] += 1

    # Generate patterns
    for conn, data in by_connection.items():
        if data["total"] < 2:
            continue
        approval_rate = round(data["approved"] / data["total"] * 100)
        if data["rejected"] > data["approved"] and data["total"] >= 3:
            patterns.append({
                "type": "high_rejection",
                "severity": "warning",
                "message": f"{conn}: {data['rejected']}/{data['total']} actions rejected ({100 - approval_rate}% rejection rate)",
                "connection": conn,
            })
        if data["amounts"]:
            avg_amt = sum(data["amounts"]) / len(data["amounts"])
            max_amt = max(data["amounts"])
            if max_amt > avg_amt * 3 and len(data["amounts"]) >= 3:
                patterns.append({
                    "type": "amount_anomaly",
                    "severity": "info",
                    "message": f"{conn}: max ${max_amt:,.0f} is 3x above average ${avg_amt:,.0f}",
                    "connection": conn,
                })
        if approval_rate == 100 and data["total"] >= 5:
            patterns.append({
                "type": "always_approved",
                "severity": "info",
                "message": f"{conn}: 100% approval rate across {data['total']} actions — consider auto-approve rule",
                "connection": conn,
            })

    for action, data in by_action.items():
        if data["avg_time"] and len(data["avg_time"]) >= 3:
            avg_t = sum(data["avg_time"]) / len(data["avg_time"])
            if avg_t > 300:  # > 5 min
                patterns.append({
                    "type": "slow_approval",
                    "severity": "warning",
                    "message": f"{action}: average approval time {avg_t/60:.0f} min — consider lowering threshold",
                    "action": action,
                })

    return {
        "patterns": patterns,
        "stats": {
            "total_jobs": len(jobs),
            "period_days": days,
            "connections_analyzed": len(by_connection),
            "actions_analyzed": len(by_action),
        },
    }

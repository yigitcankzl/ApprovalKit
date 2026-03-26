import hashlib
import json
import uuid
from datetime import datetime, timedelta

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import get_db
from api.middleware.auth import verify_hmac_signature
from api.models.workspace import Workspace
from api.models.approval_job import ApprovalJob, AuditLog, AuditEventType, JobState
from api.models.connection import ServiceConnection
from api.constants import REDIS_KEY_IDEMPOTENCY
from api.middleware.workspace import get_current_workspace
from api.services.pii import mask_text, mask_params
from api.schemas.request import ApprovalRequest, ApprovalResponse, JobStatusResponse
from api.services.rule_engine import (
    find_matching_rule,
    is_in_blackout,
    check_cooldown,
    check_pre_approval,
    check_scope_creep,
    get_required_approval_count,
    increment_cooldown,
    render_binding_message,
)

router = APIRouter(prefix="/api/v1", tags=["approval"])
settings = get_settings()


async def get_redis() -> aioredis.Redis:
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield r
    finally:
        await r.close()


@router.post("/request", response_model=ApprovalResponse, status_code=200)
async def submit_approval_request(
    request: ApprovalRequest,
    response: Response,
    workspace: Workspace = Depends(verify_hmac_signature),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    # Check idempotency (key includes params hash to prevent replay with different params)
    params_hash = hashlib.sha256(json.dumps(request.params, sort_keys=True).encode()).hexdigest()[:12]
    idem_key = f"{request.idempotency_key}:{params_hash}"
    cached = await redis_client.get(REDIS_KEY_IDEMPOTENCY.format(key=idem_key))
    if cached:
        data = json.loads(cached)
        return ApprovalResponse(**data)

    # Scope creep detection (action + amount anomaly)
    scope_creep = await check_scope_creep(
        workspace.id, request.user_id, request.connection, request.action, db,
        params=request.params,
    )
    is_new_action = scope_creep["is_new_action"]

    # Find matching rule
    rule = await find_matching_rule(
        workspace.id, request.connection, request.action, request.params, db
    )

    if not rule:
        # No rule = auto-approve
        response = ApprovalResponse(
            job_id=str(uuid.uuid4()),
            status="approved",
            message="No matching rule — auto-approved",
        )
        return response

    # Blackout check
    if is_in_blackout(rule):
        raise HTTPException(status_code=403, detail="Action blocked: blackout window active")

    # Cooldown check
    if not await check_cooldown(rule, redis_client):
        raise HTTPException(status_code=403, detail="Action blocked: cooldown limit exceeded")

    # Pre-approval check
    if await check_pre_approval(rule, request.params, redis_client):
        job = ApprovalJob(
            id=uuid.uuid4(),
            idempotency_key=request.idempotency_key,
            workspace_id=workspace.id,
            rule_id=rule.id,
            connection=request.connection,
            action=request.action,
            params=request.params,
            agent_user_id=request.user_id,
            state=JobState.PRE_APPROVED,
            required_count=1,
            completed_at=datetime.utcnow(),
        )
        db.add(job)

        audit = AuditLog(
            job_id=job.id,
            workspace_id=workspace.id,
            event_type=AuditEventType.PRE_APPROVED,
            note="Matched active pre-approval",
        )
        db.add(audit)
        await db.commit()

        response = ApprovalResponse(
            job_id=str(job.id),
            status="pre_approved",
            message="Pre-approval active",
        )
        return response

    # Create approval job (shared helper)
    job = await _create_pending_job(
        workspace, rule, request.connection, request.action, request.params,
        request.user_id, request.idempotency_key, db, redis_client,
    )

    # Scope creep audit (only for SDK requests, not test)
    if is_new_action:
        db.add(AuditLog(
            job_id=job.id, workspace_id=workspace.id,
            event_type=AuditEventType.SCOPE_CREEP,
            note=f"First time agent requests {request.connection}:{request.action}",
        ))
    if scope_creep.get("amount_anomaly"):
        db.add(AuditLog(
            job_id=job.id, workspace_id=workspace.id,
            event_type=AuditEventType.SCOPE_CREEP,
            note=f"Amount anomaly: {scope_creep['anomaly_detail']}",
        ))
    if is_new_action or scope_creep.get("amount_anomaly"):
        await db.commit()

    await increment_cooldown(rule, redis_client)

    response_data = {
        "job_id": str(job.id),
        "status": "pending",
        "message": "Approval requested — CIBA notification sent",
    }
    await redis_client.setex(REDIS_KEY_IDEMPOTENCY.format(key=idem_key), 86400, json.dumps(response_data))

    response.status_code = 202
    return ApprovalResponse(**response_data)


async def _create_pending_job(
    workspace: Workspace, rule, connection: str, action: str,
    params: dict, user_id: str, idempotency_key: str,
    db: AsyncSession, redis_client: aioredis.Redis,
) -> ApprovalJob:
    """Shared: create ApprovalJob, audit log, enqueue Celery task, publish SSE."""
    required = get_required_approval_count(rule)
    job = ApprovalJob(
        id=uuid.uuid4(),
        idempotency_key=idempotency_key,
        workspace_id=workspace.id,
        rule_id=rule.id,
        connection=connection,
        action=action,
        params=params,
        agent_user_id=user_id,
        state=JobState.PENDING,
        required_count=required,
        expires_at=datetime.utcnow() + timedelta(seconds=rule.timeout_seconds),
    )
    db.add(job)
    audit = AuditLog(
        job_id=job.id,
        workspace_id=workspace.id,
        event_type=AuditEventType.REQUESTED,
        binding_message=mask_text(render_binding_message(rule.context_template, params)),
    )
    db.add(audit)
    await db.commit()

    from api.worker.tasks import process_approval_job
    process_approval_job.delay(str(job.id))

    await redis_client.publish("approval_events", json.dumps({
        "type": "requested",
        "job_id": str(job.id),
        "connection": connection,
        "action": action,
        "timestamp": datetime.utcnow().isoformat(),
    }))
    return job


class TestRequest(ApprovalRequest):
    """Same as ApprovalRequest but with defaults for dashboard testing."""
    user_id: str = "dashboard-test"
    idempotency_key: str = ""


@router.post("/test-request", status_code=202)
async def dashboard_test_request(
    body: TestRequest,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Dashboard-initiated test request — no HMAC required."""
    if not body.idempotency_key:
        body.idempotency_key = f"test-{uuid.uuid4()}"

    rule = await find_matching_rule(workspace.id, body.connection, body.action, body.params, db)
    if not rule:
        return {"job_id": None, "status": "auto_approved", "message": "No matching rule — would auto-approve"}
    if is_in_blackout(rule):
        raise HTTPException(status_code=403, detail="Blackout window active")

    job = await _create_pending_job(
        workspace, rule, body.connection, body.action, body.params,
        body.user_id, body.idempotency_key, db, redis_client,
    )
    return {
        "job_id": str(job.id), "status": "pending",
        "message": "Test request sent — CIBA push going to approver(s)",
        "rule": rule.name, "model": rule.model.value,
    }


@router.get("/test-status/{job_id}")
async def dashboard_test_status(job_id: str, workspace: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    """Dashboard job status polling — workspace-scoped."""
    result = await db.execute(
        select(ApprovalJob).where(
            ApprovalJob.id == uuid.UUID(job_id),
            ApprovalJob.workspace_id == workspace.id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": str(job.id),
        "status": job.state.value,
        "final_params": job.final_params,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@router.patch("/jobs/{job_id}/params")
async def modify_job_params(
    job_id: str,
    body: dict,
    workspace: Workspace = Depends(verify_hmac_signature),
    db: AsyncSession = Depends(get_db),
):
    """
    Allow an approver to submit modified parameters before the CIBA approval
    is granted.  The worker reads `final_params` (falling back to `params`)
    when executing the downstream action, so calling this endpoint mid-flight
    changes what actually gets executed.
    """
    from sqlalchemy import select
    result = await db.execute(
        select(ApprovalJob).where(
            ApprovalJob.id == uuid.UUID(job_id),
            ApprovalJob.workspace_id == workspace.id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.state not in (JobState.PENDING, JobState.CIBA_SENT):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot modify params for job in state '{job.state.value}'"
        )

    modified = body.get("params")
    if not modified or not isinstance(modified, dict):
        raise HTTPException(status_code=422, detail="Body must contain 'params' dict")

    from api.constants import FORBIDDEN_PARAM_KEYS
    if FORBIDDEN_PARAM_KEYS.intersection(modified.keys()):
        raise HTTPException(status_code=422, detail="Forbidden param key detected")

    job.final_params = modified

    audit = AuditLog(
        job_id=job.id,
        workspace_id=workspace.id,
        event_type=AuditEventType.REQUESTED,
        note="params_modified by approver",
        modified_params=mask_params(modified),
    )
    db.add(audit)
    await db.commit()

    return {"status": "updated", "job_id": job_id, "final_params": modified}


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    workspace: Workspace = Depends(verify_hmac_signature),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ApprovalJob).where(
            ApprovalJob.id == uuid.UUID(job_id),
            ApprovalJob.workspace_id == workspace.id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Build execution receipt if job completed via Token Vault
    execution_receipt = None
    if job.state == JobState.APPROVED:
        conn_result = await db.execute(
            select(ServiceConnection).where(ServiceConnection.slug == job.connection)
        )
        conn = conn_result.scalar_one_or_none()
        if conn and conn.connected_auth0_user_id:
            execution_receipt = {
                "via": "auth0_token_vault",
                "connected_user": conn.connected_auth0_user_id,
                "connected_user_name": conn.connected_user_name,
                "service": conn.service,
            }

    return JobStatusResponse(
        job_id=str(job.id),
        status=job.state.value,
        approvals_count=job.approvals_count,
        required_count=job.required_count,
        final_params=job.final_params,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        execution_receipt=execution_receipt,
    )


@router.get("/jobs/pending")
async def get_pending_jobs(workspace: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    """List pending approval jobs — workspace-scoped."""
    pending_states = [
        JobState.PENDING, JobState.CIBA_SENT,
        JobState.WAITING_APPROVAL, JobState.PARTIALLY_APPROVED,
    ]
    result = await db.execute(
        select(ApprovalJob)
        .where(ApprovalJob.workspace_id == workspace.id, ApprovalJob.state.in_(pending_states))
        .order_by(ApprovalJob.created_at.desc())
        .limit(20)
    )
    jobs = result.scalars().all()

    # Get binding messages from audit log
    job_ids = [j.id for j in jobs]
    binding_map: dict = {}
    if job_ids:
        audit_result = await db.execute(
            select(AuditLog).where(
                AuditLog.job_id.in_(job_ids),
                AuditLog.event_type == AuditEventType.CIBA_SENT,
            ).order_by(AuditLog.created_at.desc())
        )
        for a in audit_result.scalars().all():
            key = str(a.job_id)
            if key not in binding_map:
                binding_map[key] = a.binding_message

    return [
        {
            "job_id": str(j.id),
            "connection": j.connection,
            "action": j.action,
            "params": j.params,
            "state": j.state.value,
            "created_at": j.created_at.isoformat(),
            "binding_message": binding_map.get(str(j.id)),
        }
        for j in jobs
    ]


@router.post("/jobs/{job_id}/decision")
async def submit_web_decision(
    job_id: str,
    body: dict,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Web-based approve/reject — workspace-scoped, rate-limited."""
    from api.middleware.rate_limit import rate_limiter
    allowed = await rate_limiter.check_rate_limit(key=f"decision:{job_id}", max_requests=5, window_seconds=60)
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many decisions for this job. Try again later.")
    result = await db.execute(
        select(ApprovalJob).where(
            ApprovalJob.id == uuid.UUID(job_id),
            ApprovalJob.workspace_id == workspace.id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    decision = body.get("decision")
    modified_params = body.get("modified_params")
    note = body.get("note") or "Approved via web dashboard"

    if decision == "approve":
        job.state = JobState.APPROVED
        job.completed_at = datetime.utcnow()
        job.approvals_count = (job.approvals_count or 0) + 1
        if modified_params:
            job.final_params = modified_params
        event_type = AuditEventType.APPROVED
    elif decision == "reject":
        job.state = JobState.REJECTED
        job.completed_at = datetime.utcnow()
        event_type = AuditEventType.REJECTED
    else:
        raise HTTPException(status_code=422, detail="decision must be 'approve' or 'reject'")

    audit = AuditLog(
        job_id=job.id,
        workspace_id=job.workspace_id,
        event_type=event_type,
        note=mask_text(note) if note else note,
        modified_params=mask_params(modified_params),
    )
    db.add(audit)
    await db.commit()

    await redis_client.publish("approval_events", json.dumps({
        "type": decision + "d",
        "job_id": job_id,
        "connection": job.connection,
        "action": job.action,
        "note": note,
        "timestamp": datetime.utcnow().isoformat(),
    }))

    # If approved, execute action via Token Vault
    execution_result = None
    if decision == "approve":
        from api.services.token_vault import token_vault_service
        execution_result = await token_vault_service.execute_action(
            connection=job.connection,
            action=job.action,
            params=modified_params or job.final_params or job.params,
            workspace_id=str(job.workspace_id),
            db=db,
        )

    return {"status": decision + "d", "job_id": job_id, "execution": execution_result}

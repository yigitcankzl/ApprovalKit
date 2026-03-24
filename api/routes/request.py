import uuid
from datetime import datetime, timedelta

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import get_db
from api.middleware.auth import verify_hmac_signature
from api.models.workspace import Workspace
from api.models.approval_job import ApprovalJob, AuditLog, AuditEventType, JobState
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


@router.post("/request", response_model=ApprovalResponse)
async def submit_approval_request(
    request: ApprovalRequest,
    workspace: Workspace = Depends(verify_hmac_signature),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    # Check idempotency
    cached = await redis_client.get(f"idem:{request.idempotency_key}")
    if cached:
        import json
        data = json.loads(cached)
        return ApprovalResponse(**data)

    # Scope creep detection
    is_new_action = await check_scope_creep(
        workspace.id, request.user_id, request.connection, request.action, db
    )

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

    # Create approval job
    required = get_required_approval_count(rule)
    job = ApprovalJob(
        id=uuid.uuid4(),
        idempotency_key=request.idempotency_key,
        workspace_id=workspace.id,
        rule_id=rule.id,
        connection=request.connection,
        action=request.action,
        params=request.params,
        agent_user_id=request.user_id,
        state=JobState.PENDING,
        required_count=required,
        expires_at=datetime.utcnow() + timedelta(seconds=rule.timeout_seconds),
    )
    db.add(job)

    # Scope creep audit
    if is_new_action:
        scope_audit = AuditLog(
            job_id=job.id,
            workspace_id=workspace.id,
            event_type=AuditEventType.SCOPE_CREEP,
            note=f"First time agent requests {request.connection}:{request.action}",
        )
        db.add(scope_audit)

    audit = AuditLog(
        job_id=job.id,
        workspace_id=workspace.id,
        event_type=AuditEventType.REQUESTED,
        binding_message=render_binding_message(rule.context_template, request.params),
    )
    db.add(audit)

    await db.commit()
    await increment_cooldown(rule, redis_client)

    # Enqueue Celery task
    from api.worker.tasks import process_approval_job
    process_approval_job.delay(str(job.id))

    import json
    response_data = {
        "job_id": str(job.id),
        "status": "pending",
        "message": "Approval requested — CIBA notification sent",
    }
    await redis_client.setex(f"idem:{request.idempotency_key}", 86400, json.dumps(response_data))

    return ApprovalResponse(**response_data)


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

    job.final_params = modified

    audit = AuditLog(
        job_id=job.id,
        workspace_id=workspace.id,
        event_type=AuditEventType.REQUESTED,
        note=f"params_modified by approver",
        modified_params=modified,
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

    return JobStatusResponse(
        job_id=str(job.id),
        status=job.state.value,
        approvals_count=job.approvals_count,
        required_count=job.required_count,
        final_params=job.final_params,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )

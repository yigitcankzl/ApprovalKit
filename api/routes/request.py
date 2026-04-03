import hashlib
import json
import uuid
from datetime import datetime, timedelta

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request as FastAPIRequest, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import get_db
from api.middleware.auth import verify_hmac_signature
from api.models.workspace import Workspace
from api.models.approval_job import ApprovalJob, AuditLog, AuditEventType, JobState
from api.models.connection import ServiceConnection
from api.models.agent import RegisteredAgent
from api.constants import REDIS_KEY_IDEMPOTENCY
from api.middleware.workspace import get_current_workspace
from api.services.pii import mask_text, mask_params
from api.schemas.request import ApprovalRequest, ApprovalResponse, JobStatusResponse
from api.services.rule_engine import (
    find_matching_rule,
    is_in_blackout,
    is_outside_allowed_days,
    check_cooldown,
    check_pre_approval,
    check_scope_creep,
    get_required_approval_count,
    increment_cooldown,
    render_binding_message,
    compute_risk_score,
    check_budget,
    record_spending,
    check_rule_budget,
    record_rule_spending,
    check_reauth_required,
    increment_reauth_counter,
    reset_reauth_counter,
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
    raw_request: FastAPIRequest,
    workspace: Workspace = Depends(verify_hmac_signature),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    # Rate limit per agent/workspace to prevent abuse
    from api.middleware.rate_limit import rate_limiter
    rate_key = f"request:{workspace.id}:{request.user_id or 'anon'}"
    allowed = await rate_limiter.check_rate_limit(key=rate_key, max_requests=60, window_seconds=60)
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded — too many approval requests. Try again later.")

    # Auto-discover agent: ensure every user_id that sends requests
    # is visible in the dashboard, regardless of auth method.
    agent = getattr(raw_request.state, "agent", None)
    if request.user_id:
        existing = await db.execute(
            select(RegisteredAgent).where(
                RegisteredAgent.workspace_id == workspace.id,
                RegisteredAgent.name == request.user_id,
                RegisteredAgent.is_active.is_(True),
            )
        )
        discovered = existing.scalar_one_or_none()
        if not discovered:
            discovered = RegisteredAgent(
                workspace_id=workspace.id,
                name=request.user_id,
                description=f"Auto-discovered from first request ({request.connection}/{request.action})",
                icon="bot",
                is_active=True,
            )
            db.add(discovered)
            await db.flush()
        if not agent:
            agent = discovered

    # Dynamic action scoping: enforce agent's allowed_connections
    if agent and agent.allowed_connections:
        allowed = agent.allowed_connections
        if isinstance(allowed, list) and request.connection not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Agent '{agent.name}' is not allowed to use connection '{request.connection}'. "
                       f"Allowed: {', '.join(allowed)}",
            )
        if isinstance(allowed, dict):
            conn_actions = allowed.get(request.connection)
            if conn_actions is None:
                raise HTTPException(
                    status_code=403,
                    detail=f"Agent '{agent.name}' is not allowed to use connection '{request.connection}'.",
                )
            if isinstance(conn_actions, list) and request.action not in conn_actions:
                raise HTTPException(
                    status_code=403,
                    detail=f"Agent '{agent.name}' cannot perform '{request.action}' on '{request.connection}'. "
                           f"Allowed actions: {', '.join(conn_actions)}",
                )

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

    # Budget check (per-agent spending limits)
    amount_val = None
    for k in ("amount", "amount_usd", "total"):
        raw = request.params.get(k)
        if raw is not None:
            try:
                amount_val = float(raw)
            except (TypeError, ValueError):
                pass
            break

    if amount_val and amount_val > 0:
        from api.constants import DEFAULT_BUDGET_LIMITS
        budget_limits = DEFAULT_BUDGET_LIMITS
        budget_result = await check_budget(
            agent_id=request.user_id,
            amount=amount_val,
            limits=budget_limits,
            redis_client=redis_client,
        )
        if not budget_result["allowed"]:
            raise HTTPException(
                status_code=403,
                detail=f"Budget exceeded: {budget_result['exceeded']} limit reached. "
                       f"Spent: ${budget_result['spent'][budget_result['exceeded']]:,.0f}",
            )

    # Find matching rule
    rule = await find_matching_rule(
        workspace.id, request.connection, request.action, request.params, db
    )

    if not rule:
        # No rule = auto-approve, execute via Token Vault immediately
        await db.commit()  # persist auto-discovered agent (if created above)
        from api.services.token_vault import token_vault_service
        exec_result = await token_vault_service.execute_action(
            connection=request.connection,
            action=request.action,
            params=request.params,
            workspace_id=str(workspace.id),
            db=db,
        )
        return ApprovalResponse(
            job_id=str(uuid.uuid4()),
            status="approved",
            message="No matching rule — auto-approved and executed",
        )

    # Blackout check
    if is_in_blackout(rule):
        raise HTTPException(status_code=403, detail="Action blocked: blackout window active")

    # Allowed days check (scheduled approvals)
    if is_outside_allowed_days(rule):
        raise HTTPException(status_code=403, detail="Action blocked: not an allowed day of week for this rule")

    # Per-rule budget check
    if amount_val and amount_val > 0 and getattr(rule, "budget_limits", None):
        rule_budget = await check_rule_budget(rule, amount_val, redis_client)
        if not rule_budget["allowed"]:
            raise HTTPException(
                status_code=403,
                detail=f"Rule budget exceeded: {rule_budget['exceeded']} limit reached for rule '{rule.name}'",
            )

    # Cooldown check
    if not await check_cooldown(rule, redis_client):
        raise HTTPException(status_code=403, detail="Action blocked: cooldown limit exceeded")

    # Re-authorization check: if consecutive approvals exceed threshold, force fresh approval
    reauth = await check_reauth_required(rule, request.user_id, request.connection, request.action, redis_client)
    reauth_forced = reauth["required"]

    # Pre-approval check (skip if re-auth is forced)
    if not reauth_forced and await check_pre_approval(rule, request.params, redis_client):
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

    # Compute risk score before creating job (Feature 7)
    risk = compute_risk_score(request.params, scope_creep=scope_creep, rule=rule)
    risk_score_val = risk.get("score", 0)
    risk_level_val = risk.get("level", "low")

    # Risk-based auto-approve: if rule has threshold and score is low enough (skip if re-auth forced)
    if (
        not reauth_forced
        and rule.risk_auto_approve_threshold is not None
        and risk_score_val <= rule.risk_auto_approve_threshold
    ):
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
            risk_score=risk_score_val,
            risk_level=risk_level_val,
        )
        db.add(job)
        db.add(AuditLog(
            job_id=job.id, workspace_id=workspace.id,
            event_type=AuditEventType.PRE_APPROVED,
            note=f"Risk auto-approve: score={risk_score_val} <= threshold={rule.risk_auto_approve_threshold}",
        ))
        await db.commit()
        response_data = {
            "job_id": str(job.id),
            "status": "pre_approved",
            "message": f"Risk score {risk_score_val} is below auto-approve threshold",
            "risk": risk,
        }
        await redis_client.setex(REDIS_KEY_IDEMPOTENCY.format(key=idem_key), 86400, json.dumps(response_data))
        return ApprovalResponse(**response_data)

    # Create approval job (shared helper)
    job = await _create_pending_job(
        workspace, rule, request.connection, request.action, request.params,
        request.user_id, request.idempotency_key, db, redis_client,
        risk_score=risk_score_val, risk_level=risk_level_val,
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

    # If re-auth was forced, add note to audit
    if reauth_forced:
        db.add(AuditLog(
            job_id=job.id, workspace_id=workspace.id,
            event_type=AuditEventType.STEP_UP,
            note=f"Re-authorization required: {reauth['consecutive']} consecutive approvals (threshold: {reauth['threshold']})",
        ))
        await db.commit()

    response_data = {
        "job_id": str(job.id),
        "status": "pending",
        "message": "Re-authorization required" if reauth_forced else "Approval requested — CIBA notification sent",
        "risk": risk,
    }
    await redis_client.setex(REDIS_KEY_IDEMPOTENCY.format(key=idem_key), 86400, json.dumps(response_data))

    response.status_code = 202
    return ApprovalResponse(**response_data)


async def _create_pending_job(
    workspace: Workspace, rule, connection: str, action: str,
    params: dict, user_id: str, idempotency_key: str,
    db: AsyncSession, redis_client: aioredis.Redis,
    risk_score: int = 0, risk_level: str = "low",
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
        risk_score=risk_score,
        risk_level=risk_level,
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
        "workspace_id": str(workspace.id),
        "timestamp": datetime.utcnow().isoformat(),
    }))
    return job


class TestRequest(ApprovalRequest):
    """Same as ApprovalRequest but with defaults for dashboard testing."""
    user_id: str = "dashboard-test"
    idempotency_key: str = "test-default"


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
        # Auto-approve: execute via Token Vault immediately
        from api.services.token_vault import token_vault_service
        exec_result = await token_vault_service.execute_action(
            connection=body.connection,
            action=body.action,
            params=body.params,
            workspace_id=str(workspace.id),
            db=db,
        )
        return {
            "job_id": None,
            "status": "auto_approved",
            "message": "No matching rule — auto-approved and executed",
            "execution": exec_result,
        }
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
        "approvals_count": job.approvals_count or 0,
        "required_count": job.required_count or 1,
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

    # Check if rule allows partial approval (param modification)
    from api.models.rule import Rule
    if job.rule_id:
        rule_result = await db.execute(select(Rule).where(Rule.id == job.rule_id))
        rule = rule_result.scalar_one_or_none()
        if rule and not rule.partial_approval:
            raise HTTPException(status_code=403, detail="This rule does not allow parameter modification")

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
        rejection_reason=getattr(job, "rejection_reason", None),
        retry_allowed=job.state not in (JobState.BLOCKED,),
        risk_score=getattr(job, "risk_score", 0) or 0,
        risk_level=getattr(job, "risk_level", "low") or "low",
        approval_expires_at=job.approval_expires_at.isoformat() if getattr(job, "approval_expires_at", None) else None,
        expires_at=job.expires_at.isoformat() if job.expires_at else None,
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
            "expires_at": j.expires_at.isoformat() if j.expires_at else None,
            "approval_expires_at": j.approval_expires_at.isoformat() if getattr(j, "approval_expires_at", None) else None,
            "binding_message": binding_map.get(str(j.id)),
            "risk_score": getattr(j, "risk_score", 0) or 0,
            "risk_level": getattr(j, "risk_level", "low") or "low",
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
    # Use SELECT FOR UPDATE to prevent race condition between concurrent decisions
    result = await db.execute(
        select(ApprovalJob).where(
            ApprovalJob.id == uuid.UUID(job_id),
            ApprovalJob.workspace_id == workspace.id,
        ).with_for_update()
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Prevent double-decision race condition (CIBA worker may have already decided)
    if job.state in (JobState.APPROVED, JobState.REJECTED, JobState.BLOCKED, JobState.TIMEOUT):
        raise HTTPException(
            status_code=409,
            detail=f"Job already in terminal state: {job.state.value}",
        )

    decision = body.get("decision")
    modified_params = body.get("modified_params")
    note = body.get("note") or "Approved via web dashboard"
    checklist_responses = body.get("checklist")  # {"amount": true, "recipient": true}

    # Load rule for checklist + partial_approval checks
    from api.models.rule import Rule
    rule = None
    if job.rule_id:
        rule_result = await db.execute(select(Rule).where(Rule.id == job.rule_id))
        rule = rule_result.scalar_one_or_none()

    # Validate checklist if rule requires it
    if decision == "approve" and rule and rule.approval_checklist:
            required_ids = {item["id"] for item in rule.approval_checklist}
            confirmed_ids = {k for k, v in (checklist_responses or {}).items() if v}
            missing = required_ids - confirmed_ids
            if missing:
                raise HTTPException(
                    status_code=422,
                    detail=f"Checklist incomplete. Please confirm: {', '.join(missing)}",
                )

    if decision == "approve":
        # Enforce partial_approval flag for param modification
        if modified_params and rule and not rule.partial_approval:
            raise HTTPException(status_code=403, detail="This rule does not allow parameter modification")
        job.state = JobState.APPROVED
        job.completed_at = datetime.utcnow()
        job.approvals_count = (job.approvals_count or 0) + 1
        if modified_params:
            job.final_params = modified_params
        # Time-boxed: set approval execution deadline
        if rule and rule.approval_expiry_seconds:
            job.approval_expires_at = datetime.utcnow() + timedelta(seconds=rule.approval_expiry_seconds)
        event_type = AuditEventType.APPROVED
    elif decision == "reject":
        job.state = JobState.REJECTED
        job.completed_at = datetime.utcnow()
        # Feature 4: store rejection reason for agent feedback
        if note and note != "Approved via web dashboard":
            job.rejection_reason = note
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
        "workspace_id": str(job.workspace_id),
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
        # Record per-rule budget spending
        if rule and getattr(rule, "budget_limits", None):
            spend_params = modified_params or job.final_params or job.params
            for k in ("amount", "amount_usd", "total"):
                raw = spend_params.get(k)
                if raw is not None:
                    try:
                        await record_rule_spending(rule, float(raw), redis_client)
                    except Exception:
                        pass
                    break

    # Update agent trust score
    try:
        from api.routes.agents import _update_trust_score
        await _update_trust_score(job.agent_user_id, job.workspace_id, decision, db)
    except Exception:
        pass  # trust score update is best-effort

    # Update re-auth counter: increment on approve, reset on reject
    try:
        if decision == "approve":
            await increment_reauth_counter(job.agent_user_id, job.connection, job.action, redis_client)
        else:
            await reset_reauth_counter(job.agent_user_id, job.connection, job.action, redis_client)
    except Exception:
        pass  # re-auth counter is best-effort

    return {"status": decision + "d", "job_id": job_id, "execution": execution_result}


@router.post("/jobs/batch-decision")
async def batch_decision(
    body: dict,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Approve or reject multiple jobs at once.

    Body: {"job_ids": ["id1", "id2", ...], "decision": "approve"|"reject", "note": "..."}

    Returns {"results": [{"job_id": ..., "status": ..., "error": ...}, ...]}.
    Max 50 jobs per batch.
    """
    job_ids = body.get("job_ids", [])
    decision = body.get("decision", "approve")
    note = body.get("note", "Batch decision")

    if not job_ids:
        raise HTTPException(status_code=400, detail="job_ids required")
    if len(job_ids) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 jobs per batch")
    if decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'reject'")

    results = []
    pending_states = {JobState.PENDING, JobState.CIBA_SENT, JobState.WAITING_APPROVAL, JobState.PARTIALLY_APPROVED}

    for jid in job_ids:
        try:
            result = await db.execute(
                select(ApprovalJob).where(
                    ApprovalJob.id == uuid.UUID(jid),
                    ApprovalJob.workspace_id == workspace.id,
                )
            )
            job = result.scalar_one_or_none()
            if not job:
                results.append({"job_id": jid, "status": "error", "error": "not_found"})
                continue
            if job.state not in pending_states:
                results.append({"job_id": jid, "status": "error", "error": f"invalid_state: {job.state.value}"})
                continue

            new_state = JobState.APPROVED if decision == "approve" else JobState.REJECTED
            job.state = new_state
            job.completed_at = datetime.utcnow()

            event_type = AuditEventType.APPROVED if decision == "approve" else AuditEventType.REJECTED
            db.add(AuditLog(
                job_id=job.id, workspace_id=workspace.id,
                event_type=event_type, note=f"Batch: {note}",
            ))

            results.append({"job_id": jid, "status": decision + "d"})
        except Exception as e:
            results.append({"job_id": jid, "status": "error", "error": str(e)})

    await db.commit()

    approved_count = sum(1 for r in results if r["status"] == "approved")
    rejected_count = sum(1 for r in results if r["status"] == "rejected")
    error_count = sum(1 for r in results if r["status"] == "error")

    return {
        "results": results,
        "summary": {
            "total": len(job_ids),
            "approved": approved_count,
            "rejected": rejected_count,
            "errors": error_count,
        },
    }

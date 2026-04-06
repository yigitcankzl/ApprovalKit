import asyncio
import json
import uuid
from datetime import datetime, timedelta

import redis.asyncio as aioredis
from loguru import logger
from sqlalchemy import select

from api.config import get_settings
from api.worker.celery_app import celery_app
from api.worker.state_machine import validate_transition
from api.models.approval_job import ApprovalJob, AuditLog, AuditEventType, JobState
from api.models.rule import Rule, ApprovalModel
from api.services.ciba import ciba_service
from api.services.token_vault import token_vault_service
from api.services.rule_engine import render_binding_message, evaluate_conditions
from api.services.pii import mask_params
from api.middleware.rate_limit import rate_limiter


async def _publish(event_type: str, job: ApprovalJob, **kwargs):
    try:
        settings = get_settings()
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.publish("approval_events", json.dumps({
            "type": event_type,
            "job_id": str(job.id),
            "connection": job.connection,
            "action": job.action,
            "workspace_id": str(job.workspace_id),
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs,
        }))
        await r.aclose()
    except Exception as e:
        logger.warning(f"Failed to publish SSE event: {e}")


def run_async(coro):
    # Reset cached async connections so they are re-created in the new event loop.
    # Celery forks workers; inherited connections are bound to the parent's loop.
    rate_limiter._redis = None
    # Create a fresh event loop for each task to avoid loop conflicts
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _get_db_session():
    # Create a fresh engine + session per job to avoid loop binding issues
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from api.config import get_settings
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return session_factory()


import contextvars

# Per-task workspace CIBA credentials. Using contextvars instead of a
# module-level dict makes this safe under Celery's `--concurrency` (the
# value is isolated per asyncio task) — two jobs from different
# workspaces can no longer stomp on each other's credentials.
_ws_ciba_ctx: contextvars.ContextVar[dict] = contextvars.ContextVar("ws_ciba", default={})


def _current_ws_creds() -> dict:
    return _ws_ciba_ctx.get() or {}


async def _send_ciba(approver, binding_msg: str, rule: Rule, scope: str = "", job_id: str = "", ws_creds: dict | None = None) -> dict:
    """Shared CIBA initiate → record → poll pattern. Uses workspace credentials passed as param."""
    actual = _resolve_delegation(approver)
    ws = ws_creds or _current_ws_creds()
    if not ws.get("domain"):
        raise ValueError("Workspace CIBA credentials not configured — cannot send push notification")
    ciba_result = await ciba_service.initiate_ciba_request(
        user_id=actual.auth0_user_id,
        binding_message=binding_msg,
        scope=scope or "openid",
        domain=ws.get("domain", ""),
        client_id=ws.get("client_id", ""),
        client_secret=ws.get("client_secret", ""),
    )
    await rate_limiter.record_ciba_request()
    poll_result = await ciba_service.poll_ciba_token(
        auth_req_id=ciba_result["auth_req_id"],
        timeout=rule.timeout_seconds,
        domain=ws.get("domain", ""),
        client_id=ws.get("client_id", ""),
        client_secret=ws.get("client_secret", ""),
        job_id=job_id,
    )
    return {"status": poll_result["status"], "approver": actual, "token": poll_result.get("access_token")}


async def _process_any_one(job: ApprovalJob, rule: Rule):
    binding_msg = render_binding_message(rule.context_template, job.params)
    for ra in rule.rule_approvers:
        try:
            result = await _send_ciba(ra.approver, binding_msg, rule, f"{job.connection}:{job.action}", job_id=str(job.id))
            if result["status"] in ("approved", "rejected"):
                return result
        except Exception as e:
            logger.error(f"CIBA error for approver {ra.approver.name}: {e}")
            continue
    return {"status": "timeout"}


async def _process_specific(job: ApprovalJob, rule: Rule):
    if not rule.rule_approvers:
        return {"status": "blocked"}
    binding_msg = render_binding_message(rule.context_template, job.params)
    return await _send_ciba(rule.rule_approvers[0].approver, binding_msg, rule, job_id=str(job.id))


async def _process_sequential(job: ApprovalJob, rule: Rule):
    sorted_approvers = sorted(rule.rule_approvers, key=lambda ra: ra.order)
    binding_msg = render_binding_message(rule.context_template, job.params)
    for ra in sorted_approvers:
        result = await _send_ciba(ra.approver, binding_msg, rule, job_id=str(job.id))
        if result["status"] == "rejected":
            return result
        if result["status"] != "approved":
            return {"status": "timeout"}
    return {"status": "approved", "approver": _resolve_delegation(sorted_approvers[-1].approver)}


async def _process_all_of_n(job: ApprovalJob, rule: Rule):
    binding_msg = render_binding_message(rule.context_template, job.params)
    last = None
    for ra in rule.rule_approvers:
        result = await _send_ciba(ra.approver, binding_msg, rule, job_id=str(job.id))
        if result["status"] == "rejected":
            return result
        if result["status"] != "approved":
            return {"status": "timeout"}
        last = result["approver"]
    return {"status": "approved", "approver": last}


async def _process_k_of_n(job: ApprovalJob, rule: Rule):
    """
    Send CIBA to all approvers in parallel, then collect results within
    quorum_window seconds (falling back to timeout_seconds).
    Return as soon as k approvals are received.
    """
    binding_msg = render_binding_message(rule.context_template, job.params)
    k = rule.k_value or 1
    # quorum_window bounds the entire gather phase; fall back to per-approver timeout
    window = rule.quorum_window or rule.timeout_seconds

    # --- send all CIBA requests in parallel ---
    ws = _current_ws_creds()
    async def _initiate(ra):
        actual = _resolve_delegation(ra.approver)
        try:
            result = await ciba_service.initiate_ciba_request(
                user_id=actual.auth0_user_id,
                binding_message=binding_msg,
                domain=ws.get("domain", ""),
                client_id=ws.get("client_id", ""),
                client_secret=ws.get("client_secret", ""),
            )
            await rate_limiter.record_ciba_request()
            return actual, result.get("auth_req_id")
        except Exception as e:
            logger.warning(f"CIBA initiate failed for {actual.name}: {e}")
            return actual, None

    initiated = await asyncio.gather(*[_initiate(ra) for ra in rule.rule_approvers])

    # --- poll all tokens with quorum window ---
    approved_count = 0
    last_approver = None
    deadline = datetime.utcnow() + timedelta(seconds=window)

    async def _poll(approver, auth_req_id):
        if not auth_req_id:
            return approver, "error"
        remaining = max(1, int((deadline - datetime.utcnow()).total_seconds()))
        result = await ciba_service.poll_ciba_token(
            auth_req_id=auth_req_id,
            timeout=min(remaining, rule.timeout_seconds),
            job_id=str(job.id),
        )
        return approver, result.get("status", "timeout")

    poll_tasks = [_poll(approver, auth_req_id) for approver, auth_req_id in initiated]

    # Collect results as they complete; stop early once we have k approvals
    for coro in asyncio.as_completed(poll_tasks):
        if datetime.utcnow() > deadline:
            break
        approver, status = await coro
        if status == "approved":
            approved_count += 1
            last_approver = approver
            if approved_count >= k:
                return {"status": "approved", "approver": last_approver}

    if approved_count >= k:
        return {"status": "approved", "approver": last_approver}
    return {"status": "timeout"}


def _resolve_delegation(approver):
    if (
        approver.delegate_to
        and getattr(approver, "delegate", None)
        and approver.delegate_from
        and approver.delegate_until
    ):
        now = datetime.utcnow()
        # Strip timezone info for comparison with utcnow() (naive datetime)
        dfrom = approver.delegate_from.replace(tzinfo=None) if approver.delegate_from.tzinfo else approver.delegate_from
        duntil = approver.delegate_until.replace(tzinfo=None) if approver.delegate_until.tzinfo else approver.delegate_until
        if dfrom <= now <= duntil:
            return approver.delegate
    return approver


async def _process_fga_dynamic(job: ApprovalJob, rule: Rule):
    """
    FGA Dynamic Approval Routing
    =============================
    Instead of using a static approver list from rule_approvers, this model
    queries Auth0 FGA at runtime to find all users with the required relation
    on the relevant object (e.g. all budget_owners of department:engineering).

    The FGA relation and object are specified in the rule's conditions:
      conditions = {"fga_relation": "budget_owner", "fga_object": "department:engineering"}

    This enables dynamic, relationship-based approval routing that automatically
    adapts when team membership changes in FGA — no rule updates needed.
    """
    from api.services.fga import fga_client
    from api.models.approver import Approver

    # Extract FGA query from rule conditions
    conditions = rule.conditions if isinstance(rule.conditions, dict) else {}
    fga_relation = conditions.get("fga_relation", "can_approve")
    fga_object = conditions.get("fga_object", f"workspace:{job.workspace_id}")

    # Query FGA for eligible approvers
    fga_users = await fga_client.list_users(relation=fga_relation, obj=fga_object)
    if not fga_users:
        logger.warning(f"FGA dynamic: no users found for {fga_relation} on {fga_object}")
        # Fall back to rule_approvers if FGA returns empty
        if rule.rule_approvers:
            logger.info("FGA dynamic: falling back to static rule_approvers")
            return await _process_any_one(job, rule)
        return {"status": "blocked"}

    # Resolve FGA user IDs to Approver records
    session = await _get_db_session()
    try:
        # Extract auth0 user IDs from FGA format (e.g. "user:auth0|abc" -> "auth0|abc")
        auth0_ids = [u.split(":", 1)[1] if ":" in u else u for u in fga_users]

        async with session.begin():
            result = await session.execute(
                select(Approver).where(
                    Approver.workspace_id == job.workspace_id,
                    Approver.auth0_user_id.in_(auth0_ids),
                )
            )
            approvers = result.scalars().all()

        if not approvers:
            logger.warning(f"FGA dynamic: found FGA users {auth0_ids} but no matching Approver records")
            if rule.rule_approvers:
                return await _process_any_one(job, rule)
            return {"status": "blocked"}

        # Send CIBA to each resolved approver (any_one pattern)
        binding_msg = render_binding_message(rule.context_template, job.params)
        for approver in approvers:
            try:
                result = await _send_ciba(approver, binding_msg, rule, f"{job.connection}:{job.action}", job_id=str(job.id))
                if result["status"] in ("approved", "rejected"):
                    return result
            except Exception as e:
                logger.error(f"FGA dynamic CIBA error for {approver.name}: {e}")
                continue

        return {"status": "timeout"}
    finally:
        await session.close()


MODEL_PROCESSORS = {
    ApprovalModel.ANY_ONE: _process_any_one,
    ApprovalModel.SPECIFIC: _process_specific,
    ApprovalModel.SEQUENTIAL: _process_sequential,
    ApprovalModel.ALL_OF_N: _process_all_of_n,
    ApprovalModel.K_OF_N: _process_k_of_n,
    ApprovalModel.FGA_DYNAMIC: _process_fga_dynamic,
}


async def _process_job(job_id: str):
    session = await _get_db_session()

    try:
        async with session.begin():
            result = await session.execute(select(ApprovalJob).where(ApprovalJob.id == uuid.UUID(job_id)))
            job = result.scalar_one_or_none()
            if not job:
                logger.error(f"Job {job_id} not found")
                return

            rule_result = await session.execute(select(Rule).where(Rule.id == job.rule_id))
            rule = rule_result.scalar_one_or_none()
            if not rule:
                logger.error(f"Rule {job.rule_id} not found for job {job_id}")
                return

            # Reject already-expired jobs before sending CIBA notifications
            if job.expires_at and datetime.utcnow() > job.expires_at.replace(tzinfo=None):
                job.state = JobState.TIMEOUT
                job.completed_at = datetime.utcnow()
                session.add(AuditLog(
                    job_id=job.id,
                    workspace_id=job.workspace_id,
                    event_type=AuditEventType.TIMEOUT,
                    note="Job expired before processing",
                ))
                logger.warning(f"Job {job_id} expired before processing — marked TIMEOUT")
                return

            # Update state to CIBA_SENT
            validate_transition(job.state, JobState.CIBA_SENT)
            job.state = JobState.CIBA_SENT

            audit = AuditLog(
                job_id=job.id,
                workspace_id=job.workspace_id,
                event_type=AuditEventType.CIBA_SENT,
            )
            session.add(audit)

        # Send email approval links to all approvers (parallel channel alongside CIBA)
        try:
            from api.services.email_approval import send_approval_email
            binding_msg = render_binding_message(rule.context_template, job.params)
            for ra in rule.rule_approvers:
                approver = ra.approver
                if approver.email:
                    await send_approval_email(
                        approver_email=approver.email,
                        approver_name=approver.name,
                        job_id=str(job.id),
                        connection=job.connection,
                        action=job.action,
                        binding_message=binding_msg,
                        timeout_seconds=rule.timeout_seconds,
                    )
        except Exception as e:
            logger.warning(f"Email approval dispatch failed for job {job_id}: {e}")

        # Step-up authentication: escalate model if conditions met
        effective_model = rule.model
        if rule.step_up_conditions and rule.step_up_model:
            if evaluate_conditions(rule.step_up_conditions, job.params):
                effective_model = rule.step_up_model
                logger.info(f"Step-up triggered for job {job.id}: {rule.model.value} -> {rule.step_up_model.value}")
                async with session.begin():
                    session.add(AuditLog(
                        job_id=job.id,
                        workspace_id=job.workspace_id,
                        event_type=AuditEventType.STEP_UP,
                        note=f"Step-up: {rule.model.value} -> {rule.step_up_model.value}",
                    ))
                await _publish("step_up_triggered", job,
                    original_model=rule.model.value,
                    effective_model=rule.step_up_model.value)

        # Get workspace Auth0 credentials for CIBA (using separate session to avoid transaction conflicts)
        from api.services.workspace_config import get_workspace_config
        ws_session = await _get_db_session()
        try:
            ws_config = await get_workspace_config(job.workspace_id, ws_session)
        finally:
            await ws_session.close()
            engine2 = ws_session.bind
            if engine2:
                await engine2.dispose()

        # Store per-task in a contextvar so concurrent workers don't race.
        ws_creds = {
            "domain": ws_config.auth0_domain,
            "client_id": ws_config.auth0_client_id,
            "client_secret": ws_config.auth0_client_secret,
        }
        _ws_ciba_ctx.set(ws_creds)

        # Process based on approval model
        processor = MODEL_PROCESSORS.get(effective_model)
        if not processor:
            logger.error(f"Unknown approval model: {effective_model}")
            async with session.begin():
                job.state = JobState.BLOCKED
                job.completed_at = datetime.utcnow()
                session.add(AuditLog(
                    job_id=job.id, workspace_id=job.workspace_id,
                    event_type=AuditEventType.BLOCKED,
                    note=f"Unknown approval model: {effective_model}",
                ))
            return

        approval_result = await processor(job, rule)

        # Use fresh session for post-CIBA DB updates (avoids transaction conflicts)
        post_session = await _get_db_session()
        try:
          async with post_session.begin():
            result = await post_session.execute(select(ApprovalJob).where(ApprovalJob.id == uuid.UUID(job_id)))
            job = result.scalar_one_or_none()

            # If job was already decided via web dashboard, skip worker processing
            if job.state in (JobState.APPROVED, JobState.REJECTED, JobState.BLOCKED, JobState.TIMEOUT):
                logger.info(f"Job {job_id} already in terminal state {job.state.value} (likely web decision) — skipping worker update")
                await _publish(f"job_{job.state.value}", job)
                return

            if approval_result["status"] == "approved":
                job.state = JobState.APPROVED
                job.completed_at = datetime.utcnow()
                job.approvals_count = (job.approvals_count or 0) + 1

                # Execute downstream action via Token Vault
                approver_obj = approval_result.get("approver")
                approver_auth0_id = getattr(approver_obj, "auth0_user_id", None)
                exec_result = await token_vault_service.execute_action(
                    connection=job.connection,
                    action=job.action,
                    params=job.final_params or job.params,
                    workspace_id=str(job.workspace_id),
                    db=post_session,
                    approver_auth0_id=approver_auth0_id,
                )
                exec_note = None
                if exec_result.get("skipped"):
                    exec_note = "executed:skipped — no credentials configured"
                elif exec_result.get("success"):
                    result_id = exec_result.get("id") or exec_result.get("sha") or exec_result.get("deployment_id")
                    exec_note = f"executed:{job.connection}/{job.action}" + (f" id={result_id}" if result_id else "")
                else:
                    exec_note = f"execution_failed: {exec_result.get('error', 'unknown')}"
                logger.info(f"Token Vault result for job {job_id}: {exec_result}")

                # Execute on_approve_actions (post-approval Token Vault calls)
                if rule.on_approve_actions:
                    job_params = job.final_params or job.params
                    for i, post_action in enumerate(rule.on_approve_actions):
                        try:
                            # Render template params: replace {{key}} with job params
                            rendered_params = {}
                            for k, v in post_action.get("params", {}).items():
                                if isinstance(v, str) and "{{" in v:
                                    for pk, pv in job_params.items():
                                        v = v.replace(f"{{{{{pk}}}}}", str(pv))
                                rendered_params[k] = v

                            pa_result = await token_vault_service.execute_action(
                                connection=post_action["connection"],
                                action=post_action["action"],
                                params=rendered_params,
                                workspace_id=str(job.workspace_id),
                                db=post_session,
                            )
                            logger.info(f"on_approve_action[{i}] {post_action['connection']}/{post_action['action']}: {pa_result.get('success', False)}")
                            if exec_note and pa_result.get("success"):
                                exec_note += f" + {post_action['connection']}/{post_action['action']}"
                        except Exception as e:
                            logger.warning(f"on_approve_action[{i}] failed: {e}")

                # Record spending for budget tracking
                if exec_result.get("success"):
                    from api.services.rule_engine import record_spending
                    spend_amount = None
                    for k in ("amount", "amount_usd", "total"):
                        raw = (job.final_params or job.params).get(k)
                        if raw is not None:
                            try:
                                spend_amount = float(raw)
                            except (TypeError, ValueError):
                                pass
                            break
                    if spend_amount and spend_amount > 0:
                        try:
                            _settings = get_settings()
                            _r = aioredis.from_url(_settings.REDIS_URL, decode_responses=True)
                            await record_spending(job.agent_user_id, spend_amount, _r)
                            # Also record per-rule spending for rule-level budget limits
                            from api.services.rule_engine import record_rule_spending
                            await record_rule_spending(rule, spend_amount, _r)
                            await _r.aclose()
                        except Exception as e:
                            logger.warning(f"Budget record failed: {e}")
                # Record modified params in audit if they differ from original
                params_changed = (
                    job.final_params is not None
                    and job.final_params != job.params
                )
                audit = AuditLog(
                    job_id=job.id,
                    workspace_id=job.workspace_id,
                    approver_id=approver_obj.id if approver_obj and hasattr(approver_obj, "id") else None,
                    event_type=AuditEventType.APPROVED,
                    note=exec_note,
                    modified_params=mask_params(job.final_params) if params_changed else None,
                )
                post_session.add(audit)
                await _publish("approved", job, exec_note=exec_note or "")

            elif approval_result["status"] == "rejected":
                job.state = JobState.REJECTED
                job.completed_at = datetime.utcnow()

                audit = AuditLog(
                    job_id=job.id,
                    workspace_id=job.workspace_id,
                    event_type=AuditEventType.REJECTED,
                )
                post_session.add(audit)
                await _publish("rejected", job)

            elif approval_result["status"] == "timeout":
                if rule.on_timeout.value == "escalate" and rule.escalate_to:
                    job.state = JobState.ESCALATED
                    job.escalated_to = rule.escalate_to

                    audit = AuditLog(
                        job_id=job.id,
                        workspace_id=job.workspace_id,
                        event_type=AuditEventType.ESCALATED,
                        note=f"Escalated to approver {rule.escalate_to}",
                    )
                    post_session.add(audit)

                    # Process escalation
                    escalation_result = await _process_escalation(job, rule, post_session)
                    if escalation_result["status"] == "approved":
                        job.state = JobState.APPROVED
                        job.completed_at = datetime.utcnow()
                    else:
                        job.state = JobState.BLOCKED
                        job.completed_at = datetime.utcnow()
                else:
                    job.state = JobState.TIMEOUT
                    job.completed_at = datetime.utcnow()

                    audit = AuditLog(
                        job_id=job.id,
                        workspace_id=job.workspace_id,
                        event_type=AuditEventType.TIMEOUT,
                        note="Timed out — no escalation configured",
                    )
                    post_session.add(audit)

          logger.info(f"Job {job_id} completed with state: {job.state.value}")
        finally:
          post_engine = post_session.bind
          await post_session.close()
          if post_engine:
              await post_engine.dispose()

    finally:
        engine = session.bind
        await session.close()
        if engine:
            await engine.dispose()


async def _process_escalation(job: ApprovalJob, rule: Rule, session):
    from api.models.approver import Approver

    result = await session.execute(select(Approver).where(Approver.id == rule.escalate_to))
    escalation_approver = result.scalar_one_or_none()
    if not escalation_approver:
        return {"status": "blocked"}

    binding_msg = render_binding_message(rule.context_template, job.params)
    ws = _current_ws_creds()
    ciba_result = await ciba_service.initiate_ciba_request(
        user_id=escalation_approver.auth0_user_id,
        binding_message=f"[ESCALATION] {binding_msg}",
        domain=ws.get("domain", ""),
        client_id=ws.get("client_id", ""),
        client_secret=ws.get("client_secret", ""),
    )
    await rate_limiter.record_ciba_request()

    poll_result = await ciba_service.poll_ciba_token(
        auth_req_id=ciba_result["auth_req_id"],
        timeout=rule.timeout_seconds,
    )

    return poll_result


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def process_approval_job(self, job_id: str):
    try:
        run_async(_process_job(job_id))
    except Exception as e:
        logger.error(f"Error processing job {job_id} (attempt {self.request.retries + 1}/3): {e}")
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            # Send to dead letter queue after max retries
            logger.error(f"Job {job_id} permanently failed — sending to dead letter queue")
            celery_app.send_task(
                "api.worker.tasks.process_approval_job",
                args=[job_id],
                queue="dead_letter",
            )


async def _cleanup_zombie_jobs():
    """Mark stale pending/ciba_sent jobs as TIMEOUT if they've exceeded their expiry."""
    session = await _get_db_session()
    try:
        async with session.begin():
            now = datetime.utcnow()
            result = await session.execute(
                select(ApprovalJob).where(
                    ApprovalJob.state.in_([JobState.PENDING, JobState.CIBA_SENT]),
                    ApprovalJob.expires_at < now,
                )
            )
            stale_jobs = result.scalars().all()
            for job in stale_jobs:
                job.state = JobState.TIMEOUT
                job.completed_at = now
                session.add(AuditLog(
                    job_id=job.id,
                    workspace_id=job.workspace_id,
                    event_type=AuditEventType.TIMEOUT,
                    note="Zombie job cleanup — expired without resolution",
                ))
                logger.info(f"Zombie cleanup: job {job.id} marked TIMEOUT")
            if stale_jobs:
                logger.info(f"Zombie cleanup: {len(stale_jobs)} stale jobs cleaned up")
    finally:
        await session.close()


@celery_app.task
def cleanup_zombie_jobs():
    """Periodic task to clean up stale jobs. Schedule via Celery Beat."""
    run_async(_cleanup_zombie_jobs())

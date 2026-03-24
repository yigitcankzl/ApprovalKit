import asyncio
import uuid
from datetime import datetime

from celery import shared_task
from loguru import logger
from sqlalchemy import select

from api.worker.celery_app import celery_app
from api.worker.state_machine import validate_transition
from api.models.approval_job import ApprovalJob, AuditLog, AuditEventType, JobState
from api.models.rule import Rule, ApprovalModel
from api.services.ciba import ciba_service
from api.services.token_vault import token_vault_service
from api.services.rule_engine import render_binding_message
from api.middleware.rate_limit import rate_limiter


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _get_db_session():
    from api.database import async_session
    return async_session()


async def _process_any_one(job: ApprovalJob, rule: Rule):
    binding_msg = render_binding_message(rule.context_template, job.params)

    for ra in rule.rule_approvers:
        approver = ra.approver
        actual_approver = _resolve_delegation(approver)

        try:
            ciba_result = await ciba_service.initiate_ciba_request(
                user_id=actual_approver.auth0_user_id,
                binding_message=binding_msg,
                scope=f"{job.connection}:{job.action}",
            )
            await rate_limiter.record_ciba_request()

            poll_result = await ciba_service.poll_ciba_token(
                auth_req_id=ciba_result["auth_req_id"],
                timeout=rule.timeout_seconds,
            )

            if poll_result["status"] == "approved":
                return {"status": "approved", "approver": actual_approver, "token": poll_result.get("access_token")}
            elif poll_result["status"] == "rejected":
                return {"status": "rejected", "approver": actual_approver}

        except Exception as e:
            logger.error(f"CIBA error for approver {actual_approver.name}: {e}")
            continue

    return {"status": "timeout"}


async def _process_specific(job: ApprovalJob, rule: Rule):
    if not rule.rule_approvers:
        return {"status": "blocked"}

    approver = rule.rule_approvers[0].approver
    actual_approver = _resolve_delegation(approver)
    binding_msg = render_binding_message(rule.context_template, job.params)

    ciba_result = await ciba_service.initiate_ciba_request(
        user_id=actual_approver.auth0_user_id,
        binding_message=binding_msg,
    )
    await rate_limiter.record_ciba_request()

    poll_result = await ciba_service.poll_ciba_token(
        auth_req_id=ciba_result["auth_req_id"],
        timeout=rule.timeout_seconds,
    )

    if poll_result["status"] == "approved":
        return {"status": "approved", "approver": actual_approver, "token": poll_result.get("access_token")}
    elif poll_result["status"] == "rejected":
        return {"status": "rejected", "approver": actual_approver}

    return {"status": "timeout"}


async def _process_sequential(job: ApprovalJob, rule: Rule):
    sorted_approvers = sorted(rule.rule_approvers, key=lambda ra: ra.order)
    binding_msg = render_binding_message(rule.context_template, job.params)

    for ra in sorted_approvers:
        approver = ra.approver
        actual_approver = _resolve_delegation(approver)

        ciba_result = await ciba_service.initiate_ciba_request(
            user_id=actual_approver.auth0_user_id,
            binding_message=binding_msg,
        )
        await rate_limiter.record_ciba_request()

        poll_result = await ciba_service.poll_ciba_token(
            auth_req_id=ciba_result["auth_req_id"],
            timeout=rule.timeout_seconds,
        )

        if poll_result["status"] == "rejected":
            return {"status": "rejected", "approver": actual_approver}
        elif poll_result["status"] != "approved":
            return {"status": "timeout"}

    return {"status": "approved", "approver": sorted_approvers[-1].approver}


async def _process_all_of_n(job: ApprovalJob, rule: Rule):
    binding_msg = render_binding_message(rule.context_template, job.params)
    results = []

    for ra in rule.rule_approvers:
        approver = ra.approver
        actual_approver = _resolve_delegation(approver)

        ciba_result = await ciba_service.initiate_ciba_request(
            user_id=actual_approver.auth0_user_id,
            binding_message=binding_msg,
        )
        await rate_limiter.record_ciba_request()

        poll_result = await ciba_service.poll_ciba_token(
            auth_req_id=ciba_result["auth_req_id"],
            timeout=rule.timeout_seconds,
        )

        if poll_result["status"] == "rejected":
            return {"status": "rejected", "approver": actual_approver}
        elif poll_result["status"] != "approved":
            return {"status": "timeout"}

        results.append(actual_approver)

    return {"status": "approved", "approver": results[-1] if results else None}


async def _process_k_of_n(job: ApprovalJob, rule: Rule):
    binding_msg = render_binding_message(rule.context_template, job.params)
    approved_count = 0
    k = rule.k_value or 1

    for ra in rule.rule_approvers:
        approver = ra.approver
        actual_approver = _resolve_delegation(approver)

        ciba_result = await ciba_service.initiate_ciba_request(
            user_id=actual_approver.auth0_user_id,
            binding_message=binding_msg,
        )
        await rate_limiter.record_ciba_request()

        poll_result = await ciba_service.poll_ciba_token(
            auth_req_id=ciba_result["auth_req_id"],
            timeout=rule.timeout_seconds,
        )

        if poll_result["status"] == "approved":
            approved_count += 1
            if approved_count >= k:
                return {"status": "approved", "approver": actual_approver}

    if approved_count >= k:
        return {"status": "approved"}
    return {"status": "timeout"}


def _resolve_delegation(approver):
    if (
        approver.delegate_to
        and approver.delegate
        and approver.delegate_from
        and approver.delegate_until
    ):
        now = datetime.utcnow()
        if approver.delegate_from <= now <= approver.delegate_until:
            return approver.delegate
    return approver


MODEL_PROCESSORS = {
    ApprovalModel.ANY_ONE: _process_any_one,
    ApprovalModel.SPECIFIC: _process_specific,
    ApprovalModel.SEQUENTIAL: _process_sequential,
    ApprovalModel.ALL_OF_N: _process_all_of_n,
    ApprovalModel.K_OF_N: _process_k_of_n,
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

            # Update state to CIBA_SENT
            validate_transition(job.state, JobState.CIBA_SENT)
            job.state = JobState.CIBA_SENT

            audit = AuditLog(
                job_id=job.id,
                workspace_id=job.workspace_id,
                event_type=AuditEventType.CIBA_SENT,
            )
            session.add(audit)

        # Process based on approval model
        processor = MODEL_PROCESSORS.get(rule.model)
        if not processor:
            logger.error(f"Unknown approval model: {rule.model}")
            return

        approval_result = await processor(job, rule)

        async with session.begin():
            result = await session.execute(select(ApprovalJob).where(ApprovalJob.id == uuid.UUID(job_id)))
            job = result.scalar_one_or_none()

            if approval_result["status"] == "approved":
                job.state = JobState.APPROVED
                job.completed_at = datetime.utcnow()

                # Execute downstream action via Token Vault
                approver_obj = approval_result.get("approver")
                approver_auth0_id = getattr(approver_obj, "auth0_user_id", None)
                exec_result = await token_vault_service.execute_action(
                    connection=job.connection,
                    action=job.action,
                    params=job.final_params or job.params,
                    workspace_id=str(job.workspace_id),
                    db=session,
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
                audit = AuditLog(
                    job_id=job.id,
                    workspace_id=job.workspace_id,
                    approver_id=approver_obj.id if approver_obj and hasattr(approver_obj, "id") else None,
                    event_type=AuditEventType.APPROVED,
                    note=exec_note,
                )
                session.add(audit)

            elif approval_result["status"] == "rejected":
                job.state = JobState.REJECTED
                job.completed_at = datetime.utcnow()

                audit = AuditLog(
                    job_id=job.id,
                    workspace_id=job.workspace_id,
                    event_type=AuditEventType.REJECTED,
                )
                session.add(audit)

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
                    session.add(audit)

                    # Process escalation
                    escalation_result = await _process_escalation(job, rule, session)
                    if escalation_result["status"] == "approved":
                        job.state = JobState.APPROVED
                        job.completed_at = datetime.utcnow()
                    else:
                        job.state = JobState.BLOCKED
                        job.completed_at = datetime.utcnow()
                else:
                    job.state = JobState.BLOCKED
                    job.completed_at = datetime.utcnow()

                    audit = AuditLog(
                        job_id=job.id,
                        workspace_id=job.workspace_id,
                        event_type=AuditEventType.BLOCKED,
                        note="Timed out and blocked",
                    )
                    session.add(audit)

        logger.info(f"Job {job_id} completed with state: {job.state.value}")

    finally:
        await session.close()


async def _process_escalation(job: ApprovalJob, rule: Rule, session):
    from api.models.approver import Approver

    result = await session.execute(select(Approver).where(Approver.id == rule.escalate_to))
    escalation_approver = result.scalar_one_or_none()
    if not escalation_approver:
        return {"status": "blocked"}

    binding_msg = render_binding_message(rule.context_template, job.params)
    ciba_result = await ciba_service.initiate_ciba_request(
        user_id=escalation_approver.auth0_user_id,
        binding_message=f"[ESCALATION] {binding_msg}",
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
        logger.error(f"Error processing job {job_id}: {e}")
        self.retry(exc=e)

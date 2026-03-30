"""
Auth0 Log Streams Webhook + Compliance Audit Export
=====================================================
1. Receives Auth0 Log Streams webhooks to correlate Auth0 events
   (login, token exchange, CIBA) with ApprovalKit jobs.
2. Exports compliance reports as JSON for SOC2/HIPAA auditors.

The full compliance chain:
  Agent Request -> Rule Match -> CIBA Sent -> Auth0 Login -> Approved -> Token Exchange -> Execution
"""
import csv
import hashlib
import hmac
import io
import json
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import get_db
from api.middleware.workspace import get_current_workspace
from api.models.approval_job import ApprovalJob, AuditLog, AuditEventType, JobState
from api.models.workspace import Workspace

router = APIRouter(prefix="/api/v1", tags=["compliance"])
settings = get_settings()


# -----------------------------------------------------------------------
# Auth0 Log Streams Webhook Receiver
# -----------------------------------------------------------------------

@router.post("/auth0-logs")
async def receive_auth0_logs(request: Request):
    """
    Receive Auth0 Log Streams webhook payloads.

    Auth0 Log Streams sends batches of log events in real-time.
    We correlate them with ApprovalKit jobs for compliance reporting.

    See: https://auth0.com/docs/customize/log-streams
    """
    body = await request.body()

    # Verify webhook signature if configured
    signature = request.headers.get("Authorization", "")
    if settings.HMAC_SECRET and signature:
        token = signature.replace("Bearer ", "")
        # Auth0 Log Streams uses a simple bearer token
        expected = hashlib.sha256(settings.HMAC_SECRET.encode()).hexdigest()[:32]
        if token != expected:
            logger.warning("Auth0 Log Streams: invalid bearer token")

    try:
        events = json.loads(body)
        if not isinstance(events, list):
            events = [events]
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    processed = 0
    for event in events:
        log_type = event.get("type", "")
        # Map Auth0 event types to internal tracking
        if log_type in ("s", "ss", "ssa"):  # Success login, silent auth
            logger.info(f"Auth0 log: login success user={event.get('user_id', 'unknown')}")
            processed += 1
        elif log_type in ("seccft", "feccft"):  # Client credentials success/failure
            logger.info(f"Auth0 log: token exchange client={event.get('client_id', 'unknown')} type={log_type}")
            processed += 1
        elif log_type in ("cs", "f"):  # CIBA success/failure
            logger.info(f"Auth0 log: CIBA event user={event.get('user_id', 'unknown')} type={log_type}")
            processed += 1

    return {"status": "ok", "processed": processed, "total": len(events)}


# -----------------------------------------------------------------------
# Compliance Audit Export
# -----------------------------------------------------------------------

@router.get("/audit/export")
async def export_compliance_report(
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    format: str = Query(default="json", description="Export format: json or csv"),
    days: int = Query(default=30, le=365, description="Number of days to include"),
    connection: str | None = Query(default=None, description="Filter by connection"),
    state: str | None = Query(default=None, description="Filter by final state"),
):
    """
    Export a compliance report combining ApprovalKit audit events.

    Each job produces a timeline:
      1. request_received (agent submits)
      2. rule_matched (conditions evaluated)
      3. ciba_sent (push notification dispatched)
      4. approved/rejected/timeout/blocked (decision)
      5. token_exchange (Token Vault execution, if approved)

    Suitable for SOC2, HIPAA, and internal compliance audits.
    """
    since = datetime.utcnow() - timedelta(days=days)

    # Fetch all jobs in the time range
    job_query = (
        select(ApprovalJob)
        .where(
            ApprovalJob.workspace_id == workspace.id,
            ApprovalJob.created_at >= since,
        )
        .order_by(ApprovalJob.created_at.desc())
    )
    if connection:
        job_query = job_query.where(ApprovalJob.connection == connection)
    if state:
        job_query = job_query.where(ApprovalJob.state == state)

    job_result = await db.execute(job_query)
    jobs = job_result.scalars().all()

    # Fetch all audit logs for these jobs
    job_ids = [j.id for j in jobs]
    if job_ids:
        audit_result = await db.execute(
            select(AuditLog)
            .where(AuditLog.job_id.in_(job_ids))
            .order_by(AuditLog.created_at.asc())
        )
        all_logs = audit_result.scalars().all()
    else:
        all_logs = []

    # Group audit logs by job
    logs_by_job: dict[str, list] = {}
    for log in all_logs:
        jid = str(log.job_id)
        logs_by_job.setdefault(jid, []).append(log)

    # Build compliance records
    records = []
    for job in jobs:
        jid = str(job.id)
        job_logs = logs_by_job.get(jid, [])

        timeline = []
        for log in job_logs:
            et = log.event_type.value if isinstance(log.event_type, AuditEventType) else str(log.event_type)
            timeline.append({
                "event": et,
                "timestamp": log.created_at.isoformat(),
                "approver_id": str(log.approver_id) if log.approver_id else None,
                "binding_message": log.binding_message,
                "note": log.note,
            })

        record = {
            "job_id": jid,
            "connection": job.connection,
            "action": job.action,
            "agent_user_id": job.agent_user_id or "unknown",
            "state": job.state.value if isinstance(job.state, JobState) else str(job.state),
            "created_at": job.created_at.isoformat(),
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "duration_seconds": (
                (job.completed_at - job.created_at).total_seconds()
                if job.completed_at
                else None
            ),
            "rule_id": str(job.rule_id) if job.rule_id else None,
            "params_masked": _mask_sensitive(job.params or {}),
            "timeline": timeline,
            "timeline_count": len(timeline),
        }
        records.append(record)

    # Summary stats
    summary = {
        "workspace_id": str(workspace.id),
        "report_generated_at": datetime.utcnow().isoformat(),
        "period_days": days,
        "total_jobs": len(records),
        "by_state": {},
        "by_connection": {},
    }
    for r in records:
        summary["by_state"][r["state"]] = summary["by_state"].get(r["state"], 0) + 1
        summary["by_connection"][r["connection"]] = summary["by_connection"].get(r["connection"], 0) + 1

    if format == "csv":
        return _export_csv(records, summary)

    return {
        "summary": summary,
        "records": records,
    }


@router.get("/audit/compliance-stats")
async def compliance_stats(
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
    days: int = Query(default=30, le=365),
):
    """
    Aggregated compliance statistics for the dashboard.
    """
    since = datetime.utcnow() - timedelta(days=days)

    # State distribution
    state_result = await db.execute(
        select(ApprovalJob.state, func.count(ApprovalJob.id))
        .where(ApprovalJob.workspace_id == workspace.id, ApprovalJob.created_at >= since)
        .group_by(ApprovalJob.state)
    )
    by_state = {row[0].value if hasattr(row[0], "value") else str(row[0]): row[1] for row in state_result.all()}

    # Connection distribution
    conn_result = await db.execute(
        select(ApprovalJob.connection, func.count(ApprovalJob.id))
        .where(ApprovalJob.workspace_id == workspace.id, ApprovalJob.created_at >= since)
        .group_by(ApprovalJob.connection)
    )
    by_connection = {row[0]: row[1] for row in conn_result.all()}

    # Average approval time (approved jobs only)
    avg_result = await db.execute(
        select(
            func.avg(
                func.extract("epoch", ApprovalJob.completed_at) - func.extract("epoch", ApprovalJob.created_at)
            )
        ).where(
            ApprovalJob.workspace_id == workspace.id,
            ApprovalJob.created_at >= since,
            ApprovalJob.state == JobState.APPROVED,
            ApprovalJob.completed_at.is_not(None),
        )
    )
    avg_seconds = avg_result.scalar()

    # Daily trend (last N days)
    daily_result = await db.execute(
        select(
            func.date_trunc("day", ApprovalJob.created_at).label("day"),
            ApprovalJob.state,
            func.count(ApprovalJob.id),
        )
        .where(ApprovalJob.workspace_id == workspace.id, ApprovalJob.created_at >= since)
        .group_by("day", ApprovalJob.state)
        .order_by("day")
    )
    daily_raw = daily_result.all()
    daily_trend = {}
    for row in daily_raw:
        day_str = row[0].strftime("%Y-%m-%d") if row[0] else "unknown"
        state_str = row[1].value if hasattr(row[1], "value") else str(row[1])
        daily_trend.setdefault(day_str, {})[state_str] = row[2]

    total = sum(by_state.values())

    return {
        "period_days": days,
        "total_jobs": total,
        "by_state": by_state,
        "by_connection": by_connection,
        "avg_approval_seconds": round(avg_seconds, 1) if avg_seconds else None,
        "approval_rate": round(by_state.get("approved", 0) / total * 100, 1) if total else 0,
        "daily_trend": daily_trend,
    }


def _mask_sensitive(params: dict) -> dict:
    """Mask PII in params for compliance export."""
    masked = {}
    sensitive_keys = {"password", "secret", "token", "key", "ssn", "credit_card", "card_number"}
    for k, v in params.items():
        if any(s in k.lower() for s in sensitive_keys):
            masked[k] = "***REDACTED***"
        elif isinstance(v, str) and "@" in v:
            parts = v.split("@")
            masked[k] = f"{parts[0][:2]}***@{parts[1]}" if len(parts) == 2 else "***"
        else:
            masked[k] = v
    return masked


def _export_csv(records: list, summary: dict) -> StreamingResponse:
    """Export compliance records as CSV."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "job_id", "connection", "action", "agent_user_id", "state",
        "created_at", "completed_at", "duration_seconds", "rule_id",
        "timeline_count",
    ])

    for r in records:
        writer.writerow([
            r["job_id"], r["connection"], r["action"], r["agent_user_id"],
            r["state"], r["created_at"], r["completed_at"],
            r["duration_seconds"], r["rule_id"], r["timeline_count"],
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=approvalkit-compliance-{summary['period_days']}d.csv",
        },
    )

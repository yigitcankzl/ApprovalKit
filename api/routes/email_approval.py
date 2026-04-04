"""
Email Approval Routes
======================
Token-based approval links — approve/reject from email, Slack, or any URL.
No Auth0 Guardian app required.
"""
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from api.config import get_settings
from api.database import get_db
from api.models.approval_job import ApprovalJob, AuditLog, AuditEventType, JobState
from api.services.email_approval import verify_approval_token, generate_approval_url
from api.services.pii import mask_text

router = APIRouter(prefix="/api/v1", tags=["email-approval"])
settings = get_settings()


class TokenVerifyResponse(BaseModel):
    valid: bool
    job_id: str | None = None
    approver_email: str | None = None


class ApprovalLinkRequest(BaseModel):
    job_id: str
    approver_email: str = "approver@company.com"
    expires_in: int = 3600


class ApprovalLinkResponse(BaseModel):
    approve_url: str
    reject_url: str
    expires_in: int


class TokenDecisionRequest(BaseModel):
    decision: str  # "approve" or "reject"
    note: str | None = None


class TokenDecisionResponse(BaseModel):
    status: str
    job_id: str
    decision: str


@router.get("/approve/verify/{token}")
async def verify_token(token: str) -> TokenVerifyResponse:
    """Verify an email approval token and return the job details."""
    result = verify_approval_token(token)
    if not result:
        return TokenVerifyResponse(valid=False)
    return TokenVerifyResponse(
        valid=True,
        job_id=result["job_id"],
        approver_email=result["approver_email"],
    )


@router.post("/approve/{token}", response_model=TokenDecisionResponse)
async def approve_via_token(
    token: str,
    body: TokenDecisionRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenDecisionResponse:
    """Submit an approval decision via a signed email token.

    This endpoint allows approvers to approve or reject a job using a
    time-limited HMAC-signed token sent via email, Slack, or any URL.
    No login or Guardian app required.
    """
    token_data = verify_approval_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid or expired approval token")

    if body.decision not in ("approve", "reject"):
        raise HTTPException(status_code=422, detail="decision must be 'approve' or 'reject'")

    job_id = token_data["job_id"]
    result = await db.execute(
        select(ApprovalJob).where(ApprovalJob.id == uuid.UUID(job_id)).with_for_update()
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.state in (JobState.APPROVED, JobState.REJECTED, JobState.BLOCKED, JobState.TIMEOUT):
        raise HTTPException(
            status_code=409,
            detail=f"Job already in terminal state: {job.state.value}",
        )

    if body.decision == "approve":
        job.state = JobState.APPROVED
        job.completed_at = datetime.utcnow()
        job.approvals_count = (job.approvals_count or 0) + 1
        event_type = AuditEventType.APPROVED
    else:
        job.state = JobState.REJECTED
        job.completed_at = datetime.utcnow()
        event_type = AuditEventType.REJECTED

    note = mask_text(body.note) if body.note else f"Decision via email token by {token_data['approver_email']}"
    audit = AuditLog(
        job_id=job.id,
        workspace_id=job.workspace_id,
        event_type=event_type,
        note=note,
    )
    db.add(audit)
    await db.commit()

    # Publish SSE event
    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            await r.publish("approval_events", json.dumps({
                "type": body.decision + "d",
                "job_id": job_id,
                "connection": job.connection,
                "action": job.action,
                "workspace_id": str(job.workspace_id),
                "timestamp": datetime.utcnow().isoformat(),
            }))
        finally:
            await r.aclose()
    except Exception:
        pass  # SSE is best-effort

    return TokenDecisionResponse(
        status="ok",
        job_id=job_id,
        decision=body.decision,
    )


@router.post("/approve/generate-link")
async def generate_link(req: ApprovalLinkRequest) -> ApprovalLinkResponse:
    """Generate approval/reject URLs for a pending job.

    These links can be sent via email, Slack, or any messaging platform.
    The approver clicks the link to approve or reject — no login required.
    """
    approve_url = generate_approval_url(req.job_id, req.approver_email, req.expires_in)
    reject_url = f"{approve_url}?decision=reject"
    return ApprovalLinkResponse(
        approve_url=approve_url,
        reject_url=reject_url,
        expires_in=req.expires_in,
    )

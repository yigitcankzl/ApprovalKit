"""
Email Approval Routes
======================
Token-based approval links — approve/reject from email, Slack, or any URL.
No Auth0 Guardian app required.
"""
import json
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import get_db
from api.middleware.auth import verify_hmac_signature
from api.middleware.rate_limit import check_api_rate_limit
from api.models.approval_job import ApprovalJob, AuditLog, AuditEventType, JobState
from api.models.workspace import Workspace
from api.services.email_approval import verify_approval_token, consume_approval_token, generate_approval_url
from api.services.pii import mask_text
from api.services.redis_pool import get_redis

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
    decision: Literal["approve", "reject"]
    note: str | None = None


class TokenDecisionResponse(BaseModel):
    status: str
    job_id: str
    decision: str


@router.get("/approve/verify/{token}", dependencies=[Depends(check_api_rate_limit)])
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


# IMPORTANT: declare /approve/generate-link BEFORE /approve/{token}.
# FastAPI matches routes in declaration order and a path parameter
# (`{token}`) would otherwise swallow the literal "generate-link".
@router.post("/approve/generate-link")
async def generate_link(
    req: ApprovalLinkRequest,
    workspace: Workspace = Depends(verify_hmac_signature),
    db: AsyncSession = Depends(get_db),
) -> ApprovalLinkResponse:
    """Generate approval/reject URLs for a pending job.

    Requires HMAC auth so that only the workspace owning the job can
    mint approval links for it. The job must belong to the caller's
    workspace — cross-tenant link minting is rejected.
    """
    if req.expires_in <= 0 or req.expires_in > 7 * 24 * 3600:
        raise HTTPException(status_code=422, detail="expires_in must be between 1 and 604800 seconds")

    try:
        job_uuid = uuid.UUID(req.job_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid job_id")

    result = await db.execute(
        select(ApprovalJob).where(
            ApprovalJob.id == job_uuid,
            ApprovalJob.workspace_id == workspace.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Job not found in this workspace")

    approve_url = generate_approval_url(req.job_id, req.approver_email, req.expires_in)
    reject_url = f"{approve_url}?decision=reject"
    return ApprovalLinkResponse(
        approve_url=approve_url,
        reject_url=reject_url,
        expires_in=req.expires_in,
    )


@router.post(
    "/approve/{token}",
    response_model=TokenDecisionResponse,
    dependencies=[Depends(check_api_rate_limit)],
)
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
    # Pydantic already enforces decision ∈ {"approve","reject"} via the
    # Literal type — by the time we get here the decision is valid. We
    # only consume the token AFTER validation so a bad body doesn't
    # burn a legitimate token.

    # Single-use: atomically verify + consume via Redis (fails closed on replay)
    token_data = await consume_approval_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid, expired, or already-used approval token")

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

    # Publish SSE event (best-effort)
    try:
        await get_redis().publish("approval_events", json.dumps({
            "type": body.decision + "d",
            "job_id": job_id,
            "connection": job.connection,
            "action": job.action,
            "workspace_id": str(job.workspace_id),
            "timestamp": datetime.utcnow().isoformat(),
        }))
    except Exception:
        pass

    return TokenDecisionResponse(
        status="ok",
        job_id=job_id,
        decision=body.decision,
    )



"""
Email Approval Routes
======================
Token-based approval links — approve/reject from email, Slack, or any URL.
No Auth0 Guardian app required.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.services.email_approval import verify_approval_token, generate_approval_url

router = APIRouter(prefix="/api/v1", tags=["email-approval"])


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

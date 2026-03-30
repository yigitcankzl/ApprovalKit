"""
Email Approval Routes
======================
Token verification endpoint for email-based approval links.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.services.email_approval import verify_approval_token

router = APIRouter(prefix="/api/v1", tags=["email-approval"])


class TokenVerifyResponse(BaseModel):
    valid: bool
    job_id: str | None = None
    approver_email: str | None = None


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

"""
Routes for the local approval channel.

Only mounted when ``APPROVAL_PROVIDER`` (or ``APPROVAL_CHANNEL``) is
``local``. Gives operators a minimal HTTP surface to inspect pending
approvals and approve/reject them without Auth0 / Guardian.

Endpoints
---------
GET  /local-approvals/{handle}          → inspect a pending request
POST /local-approvals/{handle}/approve  → mark as approved
POST /local-approvals/{handle}/reject   → mark as rejected

These endpoints are intentionally simple — production deployments
should use the Auth0 CIBA channel instead.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.providers.local.approval import (
    get_pending,
    record_decision,
)


router = APIRouter(prefix="/local-approvals", tags=["local-approvals"])


@router.get("/{handle}")
async def get_local_approval(handle: str) -> dict:
    record = await get_pending(handle)
    if not record:
        raise HTTPException(status_code=404, detail="Handle not found or expired")
    return record


@router.post("/{handle}/approve")
async def approve_local(handle: str) -> dict:
    ok = await record_decision(handle, approved=True)
    if not ok:
        raise HTTPException(status_code=404, detail="Handle not found or expired")
    return {"status": "approved", "handle": handle}


@router.post("/{handle}/reject")
async def reject_local(handle: str) -> dict:
    ok = await record_decision(handle, approved=False)
    if not ok:
        raise HTTPException(status_code=404, detail="Handle not found or expired")
    return {"status": "rejected", "handle": handle}

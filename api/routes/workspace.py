"""
Workspace management routes
============================
POST /api/v1/workspace/setup  — create or return existing workspace
GET  /api/v1/workspace        — get current workspace info (no secrets)
"""
import secrets
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from api.config import get_settings
from api.database import get_db
from api.models.workspace import Workspace

router = APIRouter(prefix="/api/v1/workspace", tags=["workspace"])
settings = get_settings()


class WorkspaceSetupRequest(BaseModel):
    name: str = "My Workspace"
    auth0_tenant: str


async def _validate_auth0(tenant: str) -> bool:
    """Verify backend can reach Auth0 with configured credentials."""
    if not settings.AUTH0_CLIENT_ID or not settings.AUTH0_CLIENT_SECRET:
        logger.warning("AUTH0_CLIENT_ID/SECRET not configured — skipping validation")
        return True
    domain = settings.AUTH0_DOMAIN or tenant
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"https://{domain}/oauth/token",
                json={
                    "client_id": settings.AUTH0_CLIENT_ID,
                    "client_secret": settings.AUTH0_CLIENT_SECRET,
                    "audience": settings.AUTH0_MGMT_API_AUDIENCE or f"https://{domain}/api/v2/",
                    "grant_type": "client_credentials",
                },
            )
            return r.status_code == 200
    except Exception as e:
        logger.warning(f"Auth0 validation failed: {e}")
        return False


@router.post("/setup")
async def setup_workspace(body: WorkspaceSetupRequest, db: AsyncSession = Depends(get_db)):
    """
    Create workspace if one doesn't exist, or return the existing one.
    api_key and hmac_secret are only included in the response on creation.
    """
    # Check if active workspace already exists
    result = await db.execute(
        select(Workspace).where(Workspace.is_active.is_(True)).limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing:
        logger.info(f"Returning existing workspace: {existing.id}")
        return {
            "workspace_id": str(existing.id),
            "name": existing.name,
            "auth0_tenant": existing.auth0_tenant,
            "created": False,
        }

    # Validate Auth0 connection
    valid = await _validate_auth0(body.auth0_tenant)
    if not valid:
        raise HTTPException(
            status_code=400,
            detail="Could not connect to Auth0 with configured credentials. Check AUTH0_CLIENT_ID and AUTH0_CLIENT_SECRET.",
        )

    api_key = secrets.token_urlsafe(32)
    hmac_secret = secrets.token_hex(32)

    workspace = Workspace(
        id=uuid.uuid4(),
        name=body.name,
        auth0_tenant=body.auth0_tenant,
        api_key=api_key,
        hmac_secret=hmac_secret,
    )
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)

    logger.info(f"Workspace created: {workspace.id}")
    return {
        "workspace_id": str(workspace.id),
        "name": workspace.name,
        "auth0_tenant": workspace.auth0_tenant,
        "api_key": api_key,
        "hmac_secret": hmac_secret,
        "created": True,
    }


@router.get("")
async def get_workspace(db: AsyncSession = Depends(get_db)):
    """Return current workspace info without sensitive fields."""
    result = await db.execute(
        select(Workspace).where(Workspace.is_active.is_(True)).limit(1)
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=404, detail="No workspace configured yet")
    return {
        "workspace_id": str(workspace.id),
        "name": workspace.name,
        "auth0_tenant": workspace.auth0_tenant,
        "is_active": workspace.is_active,
        "created_at": workspace.created_at.isoformat(),
    }

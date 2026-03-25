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
from api.services.encryption import encrypt_secret

router = APIRouter(prefix="/api/v1/workspace", tags=["workspace"])
settings = get_settings()


class WorkspaceSetupRequest(BaseModel):
    name: str = "My Workspace"
    auth0_tenant: str = ""
    # Auth0 credentials (stored in DB, not .env)
    auth0_domain: str | None = None
    auth0_m2m_client_id: str | None = None
    auth0_m2m_client_secret: str | None = None
    auth0_web_client_id: str | None = None
    auth0_web_client_secret: str | None = None
    auth0_audience: str | None = None
    # FGA credentials
    fga_api_url: str | None = None
    fga_store_id: str | None = None
    fga_model_id: str | None = None
    fga_client_id: str | None = None
    fga_client_secret: str | None = None


async def _validate_auth0(domain: str, client_id: str, client_secret: str) -> bool:
    """Verify backend can reach Auth0 with given credentials."""
    if not client_id or not client_secret or not domain:
        logger.warning("Auth0 credentials not provided — skipping validation")
        return True
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"https://{domain}/oauth/token",
                json={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "audience": f"https://{domain}/api/v2/",
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
    Create workspace with Auth0/FGA credentials stored in DB.
    If workspace exists, update its credentials.
    """
    result = await db.execute(
        select(Workspace).where(Workspace.is_active.is_(True)).limit(1)
    )
    existing = result.scalar_one_or_none()

    # Determine Auth0 domain — from body or .env fallback
    domain = body.auth0_domain or body.auth0_tenant or settings.AUTH0_DOMAIN
    m2m_id = body.auth0_m2m_client_id or settings.AUTH0_CLIENT_ID
    m2m_secret = body.auth0_m2m_client_secret or settings.AUTH0_CLIENT_SECRET

    if existing:
        # Update credentials on existing workspace (secrets encrypted at rest)
        if body.auth0_domain:
            existing.auth0_domain = body.auth0_domain
        if body.auth0_m2m_client_id:
            existing.auth0_m2m_client_id = body.auth0_m2m_client_id
        if body.auth0_m2m_client_secret:
            existing.auth0_m2m_client_secret = encrypt_secret(body.auth0_m2m_client_secret)
        if body.auth0_web_client_id:
            existing.auth0_web_client_id = body.auth0_web_client_id
        if body.auth0_web_client_secret:
            existing.auth0_web_client_secret = encrypt_secret(body.auth0_web_client_secret)
        if body.auth0_audience:
            existing.auth0_audience = body.auth0_audience
        if body.fga_api_url:
            existing.fga_api_url = body.fga_api_url
        if body.fga_store_id:
            existing.fga_store_id = body.fga_store_id
        if body.fga_model_id:
            existing.fga_model_id = body.fga_model_id
        if body.fga_client_id:
            existing.fga_client_id = body.fga_client_id
        if body.fga_client_secret:
            existing.fga_client_secret = encrypt_secret(body.fga_client_secret)
        if body.name and body.name != "My Workspace":
            existing.name = body.name
        existing.auth0_tenant = domain

        await db.commit()
        return {
            "workspace_id": str(existing.id),
            "name": existing.name,
            "auth0_tenant": existing.auth0_tenant,
            "created": False,
            "credentials_updated": True,
        }

    # Validate Auth0 connection
    valid = await _validate_auth0(domain, m2m_id, m2m_secret)
    if not valid:
        raise HTTPException(
            status_code=400,
            detail="Could not connect to Auth0 with provided credentials.",
        )

    api_key = secrets.token_urlsafe(32)
    hmac_secret = secrets.token_hex(32)

    workspace = Workspace(
        id=uuid.uuid4(),
        name=body.name,
        auth0_tenant=domain,
        api_key=api_key,
        hmac_secret=hmac_secret,
        auth0_domain=body.auth0_domain,
        auth0_m2m_client_id=body.auth0_m2m_client_id,
        auth0_m2m_client_secret=encrypt_secret(body.auth0_m2m_client_secret),
        auth0_web_client_id=body.auth0_web_client_id,
        auth0_web_client_secret=encrypt_secret(body.auth0_web_client_secret),
        auth0_audience=body.auth0_audience,
        auth0_mgmt_api_audience=f"https://{domain}/api/v2/" if domain else None,
        fga_api_url=body.fga_api_url,
        fga_store_id=body.fga_store_id,
        fga_model_id=body.fga_model_id,
        fga_client_id=body.fga_client_id,
        fga_client_secret=encrypt_secret(body.fga_client_secret),
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


@router.get("/credentials")
async def get_workspace_credentials(db: AsyncSession = Depends(get_db)):
    """Return api_key and hmac_secret for the active workspace (dashboard use only)."""
    result = await db.execute(
        select(Workspace).where(Workspace.is_active.is_(True)).limit(1)
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=404, detail="No workspace configured yet")
    return {
        "workspace_id": str(workspace.id),
        "name": workspace.name,
        "api_key": workspace.api_key,
        "hmac_secret": workspace.hmac_secret,
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
        "has_auth0_credentials": bool(workspace.auth0_domain and workspace.auth0_m2m_client_id),
        "has_fga_credentials": bool(workspace.fga_store_id),
        "created_at": workspace.created_at.isoformat(),
    }

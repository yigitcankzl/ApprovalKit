"""
Connections management routes
==============================
Manage ServiceConnections and OAuth connect flow via Auth0 Token Vault.

POST   /api/v1/connections                        — create a new connection
GET    /api/v1/connections                        — list connections
GET    /api/v1/connections/oauth/callback         — Auth0 OAuth callback (browser redirect)
GET    /api/v1/connections/{id}                   — single connection detail
GET    /api/v1/connections/{id}/connect-url       — get Auth0 OAuth authorize URL
DELETE /api/v1/connections/{id}/auth              — disconnect (clear Token Vault link)
"""
import uuid
from typing import List
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import get_db
from api.models.connection import ServiceConnection
from api.models.workspace import Workspace

settings = get_settings()

router = APIRouter(prefix="/api/v1/connections", tags=["connections"])

# ---------------------------------------------------------------------------
# Auth0 connection name and scope per service
# ---------------------------------------------------------------------------

_AUTH0_CONNECTION = {
    "github":     "github",
    "stripe":     "stripe",
    "slack":      "slack",
    "salesforce": "salesforce",
    "gmail":      "google-oauth2",
}

_SERVICE_SCOPE = {
    "github":     "openid profile email repo",
    "stripe":     "openid profile email read_write",
    "slack":      "openid profile email",
    "salesforce": "openid profile email",
    "gmail":      "openid profile email",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _conn_to_dict(c: ServiceConnection) -> dict:
    return {
        "id":                  str(c.id),
        "name":                c.name,
        "slug":                c.slug,
        "service":             c.service,
        "actions":             c.actions or [],
        "has_credentials":     c.connected_auth0_user_id is not None,
        "connected_via":       "auth0" if c.connected_auth0_user_id else None,
        "connected_user_name": c.connected_user_name,
        "is_active":           c.is_active,
        "created_at":          c.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


class CreateConnectionRequest(BaseModel):
    name: str
    service: str
    slug: str
    actions: List[str] = []


@router.post("", status_code=201)
async def create_connection(body: CreateConnectionRequest, db: AsyncSession = Depends(get_db)):
    """Create a new service connection. Used during onboarding."""
    result = await db.execute(
        select(Workspace).where(Workspace.is_active.is_(True)).limit(1)
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=400, detail="No workspace configured. Complete onboarding step 1 first.")

    existing = await db.execute(
        select(ServiceConnection).where(ServiceConnection.slug == body.slug)
    )
    conn = existing.scalar_one_or_none()
    if conn:
        return _conn_to_dict(conn)

    conn = ServiceConnection(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        name=body.name,
        service=body.service,
        slug=body.slug,
        token_vault_connection_id=body.service,
        actions=body.actions,
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    return _conn_to_dict(conn)


@router.get("")
async def list_connections(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ServiceConnection).where(ServiceConnection.is_active.is_(True))
        .order_by(ServiceConnection.name)
    )
    return [_conn_to_dict(c) for c in result.scalars().all()]


@router.get("/oauth/callback")
async def oauth_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
    """
    Auth0 redirects here after the user authorizes the social connection.
    Exchanges the code for tokens, fetches the Auth0 user profile (sub),
    stores connected_auth0_user_id on the connection, and redirects to /connections.
    """
    connection_id = state

    try:
        conn_uuid = uuid.UUID(connection_id)
    except ValueError:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/connections?error=invalid_state")

    result = await db.execute(
        select(ServiceConnection).where(ServiceConnection.id == conn_uuid)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/connections?error=connection_not_found")

    callback_url = f"{settings.CALLBACK_BASE_URL}/api/v1/connections/oauth/callback"

    async with httpx.AsyncClient(timeout=15) as client:
        # Exchange authorization code for tokens
        token_resp = await client.post(
            f"https://{settings.AUTH0_DOMAIN}/oauth/token",
            json={
                "grant_type":    "authorization_code",
                "client_id":     settings.AUTH0_CLIENT_ID,
                "client_secret": settings.AUTH0_CLIENT_SECRET,
                "code":          code,
                "redirect_uri":  callback_url,
            },
        )
        if token_resp.status_code != 200:
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/connections?error=token_exchange_failed"
            )
        tokens = token_resp.json()
        access_token = tokens.get("access_token")

        # Fetch user profile to get sub (auth0_user_id) and display name
        userinfo_resp = await client.get(
            f"https://{settings.AUTH0_DOMAIN}/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_resp.status_code != 200:
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/connections?error=userinfo_failed"
            )
        userinfo = userinfo_resp.json()

    sub  = userinfo.get("sub", "")   # e.g. "github|12345678" or "stripe|acct_..."
    name = userinfo.get("nickname") or userinfo.get("name") or userinfo.get("email") or sub

    conn.connected_auth0_user_id = sub
    conn.connected_user_name = name
    await db.commit()

    return RedirectResponse(url=f"{settings.FRONTEND_URL}/connections?connected={conn.slug}")


@router.get("/{connection_id}/connect-url")
async def get_connect_url(connection_id: str, db: AsyncSession = Depends(get_db)):
    """
    Returns the Auth0 authorization URL that initiates the OAuth connect flow
    for the connection's service. Frontend redirects the browser to this URL.
    """
    result = await db.execute(
        select(ServiceConnection).where(ServiceConnection.id == uuid.UUID(connection_id))
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    service = conn.service.lower()
    auth0_connection = _AUTH0_CONNECTION.get(service)
    if not auth0_connection:
        raise HTTPException(
            status_code=400,
            detail=f"Service '{service}' does not support Auth0 OAuth connect. "
                   f"Supported: {', '.join(_AUTH0_CONNECTION.keys())}",
        )

    scope = _SERVICE_SCOPE.get(service, "openid profile email")
    callback_url = f"{settings.CALLBACK_BASE_URL}/api/v1/connections/oauth/callback"

    params = urlencode({
        "client_id":     settings.AUTH0_CLIENT_ID,
        "response_type": "code",
        "scope":         scope,
        "connection":    auth0_connection,
        "state":         connection_id,
        "redirect_uri":  callback_url,
    })
    url = f"https://{settings.AUTH0_DOMAIN}/authorize?{params}"

    return {"url": url, "service": service, "connection": auth0_connection}


@router.get("/{connection_id}")
async def get_connection(connection_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ServiceConnection).where(ServiceConnection.id == uuid.UUID(connection_id))
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    return _conn_to_dict(conn)


@router.delete("/{connection_id}/auth", status_code=200)
async def disconnect_auth(connection_id: str, db: AsyncSession = Depends(get_db)):
    """Remove the Auth0 Token Vault link from this connection."""
    result = await db.execute(
        select(ServiceConnection).where(ServiceConnection.id == uuid.UUID(connection_id))
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    conn.connected_auth0_user_id = None
    conn.connected_user_name = None
    await db.commit()
    return {"status": "disconnected", "connection": conn.name}

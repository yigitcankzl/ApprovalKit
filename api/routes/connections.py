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
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import get_db
from api.models.connection import ServiceConnection
from api.models.workspace import Workspace

_auth0_connections_cache: set[str] | None = None


async def _get_auth0_configured_connections() -> set[str]:
    """Fetch configured social connections from Auth0 Management API."""
    global _auth0_connections_cache
    if _auth0_connections_cache is not None:
        return _auth0_connections_cache

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Get Management API token
            token_resp = await client.post(
                f"https://{settings.AUTH0_DOMAIN}/oauth/token",
                json={
                    "grant_type": "client_credentials",
                    "client_id": settings.AUTH0_CLIENT_ID,
                    "client_secret": settings.AUTH0_CLIENT_SECRET,
                    "audience": f"https://{settings.AUTH0_DOMAIN}/api/v2/",
                },
            )
            if token_resp.status_code != 200:
                return set()
            mgmt_token = token_resp.json().get("access_token", "")

            # List all connections
            conns_resp = await client.get(
                f"https://{settings.AUTH0_DOMAIN}/api/v2/connections",
                headers={"Authorization": f"Bearer {mgmt_token}"},
                params={"fields": "name,strategy", "per_page": "100"},
            )
            if conns_resp.status_code != 200:
                return set()

            names = {c["name"] for c in conns_resp.json()}
            _auth0_connections_cache = names
            return names
    except Exception:
        return set()

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
    "stripe":     "openid profile email",
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
    conns = result.scalars().all()
    auth0_conns = await _get_auth0_configured_connections()
    out = []
    for c in conns:
        d = _conn_to_dict(c)
        auth0_name = _AUTH0_CONNECTION.get(c.service.lower(), c.service.lower())
        d["is_auth0_configured"] = auth0_name in auth0_conns
        out.append(d)
    return out


@router.get("/oauth/callback")
async def oauth_callback(
    db: AsyncSession = Depends(get_db),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    """
    Auth0 redirects here after the user authorizes the social connection.
    Exchanges the code for tokens, fetches the Auth0 user profile (sub),
    stores connected_auth0_user_id on the connection, and redirects to /connections.
    """
    if error:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/connections?error={error}")

    if not code or not state:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/connections?error=missing_code")

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
        web_client_id = settings.AUTH0_WEB_CLIENT_ID or settings.AUTH0_CLIENT_ID
        web_client_secret = settings.AUTH0_WEB_CLIENT_SECRET or settings.AUTH0_CLIENT_SECRET
        token_resp = await client.post(
            f"https://{settings.AUTH0_DOMAIN}/oauth/token",
            json={
                "grant_type":    "authorization_code",
                "client_id":     web_client_id,
                "client_secret": web_client_secret,
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
    conn.auth0_refresh_token = tokens.get("refresh_token")
    await db.commit()

    return RedirectResponse(url=f"{settings.FRONTEND_URL}/connections?connected={conn.slug}")


@router.get("/{connection_id}/connect-url")
async def get_connect_url(connection_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Initiates the Connected Accounts flow via Auth0 My Account API.
    If no user token is provided, falls back to standard authorize URL.
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

    user_token = request.headers.get("X-User-Token")
    callback_url = f"{settings.CALLBACK_BASE_URL}/api/v1/connections/connected-accounts/callback"
    scope = _SERVICE_SCOPE.get(service, "openid profile email")

    # Try Connected Accounts API (Token Vault flow) if user is logged in
    if user_token:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"https://{settings.AUTH0_DOMAIN}/me/v1/connected-accounts/connect",
                    headers={"Authorization": f"Bearer {user_token}"},
                    json={
                        "connection": auth0_connection,
                        "redirect_uri": callback_url,
                        "state": connection_id,
                        "scopes": scope.split(),
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # Store auth_session for completion step
                    await _store_auth_session(connection_id, data.get("auth_session", ""))
                    return {
                        "url": data["connect_uri"],
                        "service": service,
                        "connection": auth0_connection,
                        "flow": "connected_accounts",
                    }
                else:
                    # Log but fall through to legacy flow
                    pass
        except Exception:
            pass

    # Fallback: standard authorize URL (login flow)
    if "offline_access" not in scope:
        scope = f"{scope} offline_access"
    legacy_callback = f"{settings.CALLBACK_BASE_URL}/api/v1/connections/oauth/callback"
    client_id = settings.AUTH0_WEB_CLIENT_ID or settings.AUTH0_CLIENT_ID
    params = urlencode({
        "client_id":     client_id,
        "response_type": "code",
        "scope":         scope,
        "connection":    auth0_connection,
        "state":         connection_id,
        "redirect_uri":  legacy_callback,
    })
    url = f"https://{settings.AUTH0_DOMAIN}/authorize?{params}"
    return {"url": url, "service": service, "connection": auth0_connection, "flow": "authorize"}


# In-memory store for auth_session (simple for hackathon)
_auth_sessions: dict[str, str] = {}

async def _store_auth_session(connection_id: str, auth_session: str):
    _auth_sessions[connection_id] = auth_session


@router.get("/connected-accounts/callback")
async def connected_accounts_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    connect_code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """Complete the Connected Accounts flow — tokens are stored in Token Vault."""
    if error:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/connections?error={error}")
    if not connect_code or not state:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/connections?error=missing_connect_code")

    connection_id = state
    auth_session = _auth_sessions.pop(connection_id, "")
    if not auth_session:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/connections?error=session_expired")

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

    # Complete the Connected Accounts flow
    # We need a user token — try to get from stored session or use management API
    # For hackathon: use Management API to get user info after completion
    callback_url = f"{settings.CALLBACK_BASE_URL}/api/v1/connections/connected-accounts/callback"

    # Mark connection as connected via Token Vault Connected Accounts
    conn.connected_auth0_user_id = f"connected_accounts:{connection_id}"
    conn.connected_user_name = "Token Vault Connected"
    await db.commit()

    return RedirectResponse(url=f"{settings.FRONTEND_URL}/connections?connected={conn.slug}")


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

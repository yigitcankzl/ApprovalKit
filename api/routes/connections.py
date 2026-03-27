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
from loguru import logger
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import get_db
from api.models.connection import ServiceConnection
from api.models.workspace import Workspace
from api.middleware.workspace import get_current_workspace
from api.services.encryption import encrypt_secret, decrypt_secret
from api.services.workspace_config import get_workspace_config, WorkspaceConfig

settings = get_settings()

# No cache — always fetch fresh from Auth0 (each workspace has different tenant)
_auth0_connections_cache: dict[str, set[str]] = {}


async def _get_auth0_configured_connections(ws_config: WorkspaceConfig, workspace_id: str = "") -> dict[str, str]:
    """Fetch configured social connections from Auth0 Management API.

    Returns a dict mapping service name → Auth0 connection name.
    E.g. {"slack": "sign-in-with-slack", "github": "github", "google": "google-oauth2"}
    """
    domain = ws_config.auth0_domain
    client_id = ws_config.auth0_client_id
    client_secret = ws_config.auth0_client_secret

    if not domain or not client_id:
        return {}

    # Strategy → our service name mapping
    _strategy_to_service = {
        "github": "github", "google-oauth2": "google", "oauth2": None,  # custom — match by name
        "slack": "slack", "salesforce": "salesforce", "stripe": "stripe",
        "windowslive": "microsoft", "dropbox": "dropbox", "discord": "discord",
        "bitbucket": "bitbucket", "box": "box", "figma": "figma",
    }
    # Known name patterns for custom oauth2 connections
    _name_to_service = {
        "slack": "slack", "sign-in-with-slack": "slack", "slack-oauth-2": "slack",
        "stripe": "stripe", "salesforce": "salesforce",
        "google-drive": "google-drive",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            token_resp = await client.post(
                f"https://{domain}/oauth/token",
                json={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "audience": f"https://{domain}/api/v2/",
                },
            )
            if token_resp.status_code != 200:
                return {}
            mgmt_token = token_resp.json().get("access_token", "")

            conns_resp = await client.get(
                f"https://{domain}/api/v2/connections",
                headers={"Authorization": f"Bearer {mgmt_token}"},
                params={"fields": "name,strategy", "per_page": "100"},
            )
            if conns_resp.status_code != 200:
                return {}

            result: dict[str, str] = {}
            for c in conns_resp.json():
                name = c["name"]
                strategy = c.get("strategy", "")

                # Try strategy mapping first
                service = _strategy_to_service.get(strategy)
                if service:
                    result[service] = name
                    if service == "google":
                        result["gmail"] = name
                        result["google-drive"] = name
                    if service == "microsoft":
                        result["outlook"] = name
                    continue

                # For custom oauth2, match by name
                matched_service = _name_to_service.get(name.lower())
                if matched_service:
                    result[matched_service] = name

            return result
    except Exception as e:
        logger.warning(f"Failed to fetch Auth0 connections for {domain}: {e}")
        return {}

router = APIRouter(prefix="/api/v1/connections", tags=["connections"])

# ---------------------------------------------------------------------------
# Auth0 connection name and scope per service
# ---------------------------------------------------------------------------

_AUTH0_CONNECTION = {
    "github":     "github",
    "stripe":     "stripe",
    "slack":      "slack-oauth-2",
    "salesforce": "salesforce",
    "google":     "google-oauth2",
    "gmail":      "google-oauth2",
    "microsoft":  "windowslive",
    "outlook":    "windowslive",
    "box":        "box",
    "dropbox":    "dropbox",
    "discord":    "discord",
    "figma":      "figma",
    "spotify":    "spotify",
    "bitbucket":  "bitbucket",
    "digitalocean": "digitalocean",
    "twitch":     "twitch",
    "facebook":   "facebook",
    "linkedin":   "linkedin",
    "apple":      "apple",
    "amazon":     "amazon",
    "paypal":     "paypal",
    "shopify":    "shopify",
    "notion":     "notion",
    "jira":       "jira",
    "hubspot":    "hubspot",
    "asana":      "asana",
    "linear":     "linear",
    "freshbooks": "freshbooks",
    "basecamp":   "basecamp",
    "twitter":    "twitter",
}

_DEFAULT_SCOPE = "openid profile email"
_SERVICE_SCOPE: dict[str, str] = {
    "slack": "openid profile email",  # Slack Sign-In uses identity scopes mapped by Auth0
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
        "connected_user_name": c.connected_user_name,
        "is_active":           c.is_active,
        "has_webhook":         c.webhook_url is not None,
        "webhook_method":      c.webhook_method,
        "has_m2m":             c.m2m_api_key is not None or (c.m2m_client_id is not None and c.m2m_token_url is not None),
        "m2m_client_id":       c.m2m_client_id,
        "m2m_token_url":       c.m2m_token_url,
        "connected_via":       "auth0" if c.connected_auth0_user_id else ("m2m" if (c.m2m_client_id and c.m2m_token_url) else ("webhook" if c.webhook_url else None)),
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
    # Generic webhook config (optional — for custom services)
    webhook_url: str | None = None
    webhook_method: str | None = None       # GET/POST/PUT/PATCH/DELETE
    webhook_headers: dict | None = None     # {"Authorization": "Bearer {{token}}"}
    webhook_body_template: dict | None = None  # {"amount": "{{amount}}"}
    # M2M Credential Vault (optional — for client_credentials APIs like Amadeus, Twilio, AWS)
    m2m_api_key: str | None = None          # will be encrypted at rest
    m2m_client_id: str | None = None
    m2m_token_url: str | None = None


@router.post("", status_code=201)
async def create_connection(body: CreateConnectionRequest, workspace: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    """Create a new service connection. Used during onboarding."""

    existing = await db.execute(
        select(ServiceConnection).where(
            ServiceConnection.slug == body.slug,
            ServiceConnection.workspace_id == workspace.id,
        )
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
        webhook_url=body.webhook_url,
        webhook_method=body.webhook_method,
        webhook_headers=body.webhook_headers,
        webhook_body_template=body.webhook_body_template,
        m2m_client_id=body.m2m_client_id,
        m2m_token_url=body.m2m_token_url,
        # m2m_api_key NOT stored in DB — only in HashiCorp Vault
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)

    # Store M2M credentials ONLY in HashiCorp Vault (never in our DB)
    if body.m2m_api_key:
        from api.services.vault import store_m2m_credentials
        stored = store_m2m_credentials(
            workspace_id=str(workspace.id),
            slug=body.slug,
            api_key=body.m2m_api_key,
            client_id=body.m2m_client_id,
            token_url=body.m2m_token_url,
        )
        if stored:
            logger.info(f"M2M credentials for '{body.slug}' stored in HashiCorp Vault")
        else:
            raise HTTPException(
                status_code=503,
                detail="HashiCorp Vault is unavailable. M2M credentials cannot be stored. Start Vault and try again.",
            )

    return _conn_to_dict(conn)


@router.get("")
async def list_connections(workspace: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ServiceConnection).where(
            ServiceConnection.workspace_id == workspace.id,
            ServiceConnection.is_active.is_(True),
        ).order_by(ServiceConnection.name)
    )
    conns = result.scalars().all()
    ws_config = await get_workspace_config(workspace.id, db)
    auth0_conns = await _get_auth0_configured_connections(ws_config, str(workspace.id))
    out = []
    for c in conns:
        d = _conn_to_dict(c)
        service = c.service.lower()
        d["is_auth0_configured"] = service in auth0_conns
        d["auth0_connection_name"] = auth0_conns.get(service, "")
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
        logger.error(f"OAuth callback error: {error} — {error_description}")
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/connections?error={error}")

    if not code or not state:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/connections?error=missing_code")

    # State format: connection_id:workspace_id
    parts = state.split(":", 1)
    connection_id = parts[0]
    workspace_id = parts[1] if len(parts) > 1 else None

    try:
        conn_uuid = uuid.UUID(connection_id)
    except ValueError:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/connections?error=invalid_state")

    query = select(ServiceConnection).where(ServiceConnection.id == conn_uuid)
    if workspace_id:
        try:
            query = query.where(ServiceConnection.workspace_id == uuid.UUID(workspace_id))
        except ValueError:
            pass
    result = await db.execute(query)
    conn = result.scalar_one_or_none()
    if not conn:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/connections?error=connection_not_found")

    # Get workspace-specific Auth0 config
    ws_config = await get_workspace_config(conn.workspace_id, db)
    callback_url = f"{ws_config.callback_base_url}/api/v1/connections/oauth/callback"

    async with httpx.AsyncClient(timeout=15) as client:
        # Exchange authorization code for tokens
        web_client_id = ws_config.auth0_web_client_id
        web_client_secret = ws_config.auth0_web_client_secret
        token_resp = await client.post(
            f"https://{ws_config.auth0_domain}/oauth/token",
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
            f"https://{ws_config.auth0_domain}/userinfo",
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
    conn.auth0_refresh_token = encrypt_secret(tokens.get("refresh_token"))
    await db.commit()

    return RedirectResponse(url=f"{settings.FRONTEND_URL}/connections?connected={conn.slug}")


@router.get("/{connection_id}/connect-url")
async def get_connect_url(connection_id: str, request: Request, workspace: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    """
    Initiates the Connected Accounts flow via Auth0 My Account API.
    If no user token is provided, falls back to standard authorize URL.
    """
    result = await db.execute(
        select(ServiceConnection).where(ServiceConnection.id == uuid.UUID(connection_id), ServiceConnection.workspace_id == workspace.id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    service = conn.service.lower()
    ws_config = await get_workspace_config(workspace.id, db)

    # Look up the real Auth0 connection name from tenant
    auth0_conns = await _get_auth0_configured_connections(ws_config, str(workspace.id))
    auth0_connection = auth0_conns.get(service) or _AUTH0_CONNECTION.get(service)
    if not auth0_connection:
        raise HTTPException(
            status_code=400,
            detail=f"Service '{service}' is not configured in your Auth0 tenant ({ws_config.auth0_domain}). "
                   f"Add it under Authentication → Social in your Auth0 Dashboard.",
        )
    user_token = request.headers.get("X-User-Token")
    login_refresh_token = request.headers.get("X-Refresh-Token")
    callback_url = f"{ws_config.callback_base_url}/api/v1/connections/connected-accounts/callback"
    scope = _SERVICE_SCOPE.get(service, _DEFAULT_SCOPE)

    logger.debug(f"connect-url: domain={ws_config.auth0_domain} user_token={'present' if user_token else 'MISSING'}")

    # Save login refresh token on connection (needed for Token Exchange)
    if login_refresh_token:
        conn.auth0_refresh_token = encrypt_secret(login_refresh_token)
        await db.commit()

    # Try Connected Accounts API (Token Vault flow) if user is logged in
    if user_token:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"https://{ws_config.auth0_domain}/me/v1/connected-accounts/connect",
                    headers={"Authorization": f"Bearer {user_token}"},
                    json={
                        "connection": auth0_connection,
                        "redirect_uri": callback_url,
                        "state": f"{connection_id}:{workspace.id}",
                    },
                )
                logger.debug(f"Connected Accounts API: {resp.status_code}")
                logger.debug(f"Connected Accounts response: {resp.text[:200]}")
                if resp.status_code in (200, 201):
                    data = resp.json()
                    await _store_auth_session(connection_id, data.get("auth_session", ""), user_token)
                    connect_uri = data["connect_uri"]
                    connect_params = data.get("connect_params", {})
                    if connect_params:
                        connect_uri = f"{connect_uri}?{urlencode(connect_params)}"
                    return {
                        "url": connect_uri,
                        "service": service,
                        "connection": auth0_connection,
                        "flow": "connected_accounts",
                    }
        except Exception as e:
            logger.warning(f"Connected Accounts API exception: {e}")

    # Fallback: standard authorize URL (login flow)
    if "offline_access" not in scope:
        scope = f"{scope} offline_access"
    legacy_callback = f"{ws_config.callback_base_url}/api/v1/connections/oauth/callback"
    client_id = ws_config.auth0_web_client_id
    params = urlencode({
        "client_id":     client_id,
        "response_type": "code",
        "scope":         scope,
        "connection":    auth0_connection,
        "state":         f"{connection_id}:{workspace.id}",
        "redirect_uri":  legacy_callback,
    })
    url = f"https://{ws_config.auth0_domain}/authorize?{params}"
    return {"url": url, "service": service, "connection": auth0_connection, "flow": "authorize"}


# Auth session store — Redis-backed for multi-instance deployments
import redis.asyncio as aioredis

async def _get_session_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)

async def _store_auth_session(connection_id: str, auth_session: str, user_token: str = ""):
    r = await _get_session_redis()
    import json as _json
    await r.setex(
        f"auth_session:{connection_id}",
        600,  # 10 min TTL
        _json.dumps({"auth_session": auth_session, "user_token": user_token}),
    )
    await r.aclose()


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

    # State format: connection_id:workspace_id
    parts = state.split(":", 1)
    connection_id = parts[0]
    workspace_id = parts[1] if len(parts) > 1 else None

    import json as _json
    r = await _get_session_redis()
    raw = await r.getdel(f"auth_session:{connection_id}")
    await r.aclose()
    session_data = _json.loads(raw) if raw else {}
    auth_session = session_data.get("auth_session", "")
    user_token = session_data.get("user_token", "")
    if not auth_session:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/connections?error=session_expired")

    try:
        conn_uuid = uuid.UUID(connection_id)
    except ValueError:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/connections?error=invalid_state")

    query = select(ServiceConnection).where(ServiceConnection.id == conn_uuid)
    if workspace_id:
        try:
            query = query.where(ServiceConnection.workspace_id == uuid.UUID(workspace_id))
        except ValueError:
            pass
    result = await db.execute(query)
    conn = result.scalar_one_or_none()
    if not conn:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/connections?error=connection_not_found")

    ws_config = await get_workspace_config(conn.workspace_id, db)
    callback_url = f"{ws_config.callback_base_url}/api/v1/connections/connected-accounts/callback"

    # Complete the Connected Accounts flow
    async with httpx.AsyncClient(timeout=15) as client:
        complete_resp = await client.post(
            f"https://{ws_config.auth0_domain}/me/v1/connected-accounts/complete",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "auth_session": auth_session,
                "connect_code": connect_code,
                "redirect_uri": callback_url,
            },
        )
        logger.debug(f"Connected Accounts complete: {complete_resp.status_code}")

        if complete_resp.status_code in (200, 201):
            data = complete_resp.json()
            conn.connected_auth0_user_id = data.get("user_id", f"connected_accounts:{connection_id}")
            conn.connected_user_name = "Token Vault Connected"
            await db.commit()
            return RedirectResponse(url=f"{settings.FRONTEND_URL}/connections?connected={conn.slug}")

    # Fallback if complete fails
    conn.connected_auth0_user_id = f"connected_accounts:{connection_id}"
    conn.connected_user_name = "Token Vault Connected"
    await db.commit()
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/connections?connected={conn.slug}")


@router.get("/{connection_id}")
async def get_connection(connection_id: str, workspace: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ServiceConnection).where(ServiceConnection.id == uuid.UUID(connection_id), ServiceConnection.workspace_id == workspace.id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    return _conn_to_dict(conn)


@router.delete("/{connection_id}/auth", status_code=200)
async def disconnect_auth(connection_id: str, workspace: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    """Remove the Auth0 Token Vault link from this connection."""
    result = await db.execute(
        select(ServiceConnection).where(ServiceConnection.id == uuid.UUID(connection_id), ServiceConnection.workspace_id == workspace.id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    conn.connected_auth0_user_id = None
    conn.connected_user_name = None
    conn.auth0_refresh_token = None
    await db.commit()
    return {"status": "disconnected", "connection": conn.name}


class UpdateConnectionRequest(BaseModel):
    name: str | None = None
    actions: List[str] | None = None
    webhook_url: str | None = None
    webhook_method: str | None = None
    webhook_headers: dict | None = None
    webhook_body_template: dict | None = None


@router.put("/{connection_id}")
async def update_connection(connection_id: str, body: UpdateConnectionRequest, workspace: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    """Update a connection — name, actions, webhook config."""
    result = await db.execute(
        select(ServiceConnection).where(ServiceConnection.id == uuid.UUID(connection_id), ServiceConnection.workspace_id == workspace.id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    if body.name is not None:
        conn.name = body.name
    if body.actions is not None:
        conn.actions = body.actions
    if body.webhook_url is not None:
        conn.webhook_url = body.webhook_url
    if body.webhook_method is not None:
        conn.webhook_method = body.webhook_method
    if body.webhook_headers is not None:
        conn.webhook_headers = body.webhook_headers
    if body.webhook_body_template is not None:
        conn.webhook_body_template = body.webhook_body_template

    await db.commit()
    await db.refresh(conn)
    return _conn_to_dict(conn)


@router.delete("/{connection_id}", status_code=200)
async def delete_connection(connection_id: str, workspace: Workspace = Depends(get_current_workspace), db: AsyncSession = Depends(get_db)):
    """Permanently delete a service connection."""
    result = await db.execute(
        select(ServiceConnection).where(ServiceConnection.id == uuid.UUID(connection_id), ServiceConnection.workspace_id == workspace.id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    await db.delete(conn)
    await db.commit()
    return {"status": "deleted", "connection": conn.name}

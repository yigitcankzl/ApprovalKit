"""
Workspace-aware configuration
==============================
Reads Auth0/FGA credentials from workspace DB record, falls back to .env.
Each organization stores its own credentials — no .env editing needed.
"""
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.models.workspace import Workspace
from api.services.encryption import decrypt_secret

settings = get_settings()


@dataclass
class WorkspaceConfig:
    auth0_domain: str
    auth0_client_id: str
    auth0_client_secret: str
    auth0_web_client_id: str
    auth0_web_client_secret: str
    auth0_audience: str
    auth0_mgmt_api_audience: str
    fga_api_url: str
    fga_store_id: str
    fga_model_id: str
    fga_client_id: str
    fga_client_secret: str
    credentials_key: str
    callback_base_url: str
    frontend_url: str


async def get_workspace_config(workspace_id: UUID, db: AsyncSession) -> WorkspaceConfig:
    """Build config from workspace DB record with .env fallback."""
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    ws = result.scalar_one_or_none()

    def _pick(ws_val, env_val):
        return ws_val if ws_val else (env_val or "")

    if ws:
        domain = _pick(ws.auth0_domain, settings.AUTH0_DOMAIN)
        return WorkspaceConfig(
            auth0_domain=domain,
            auth0_client_id=_pick(ws.auth0_m2m_client_id, settings.AUTH0_CLIENT_ID),
            auth0_client_secret=_pick(decrypt_secret(ws.auth0_m2m_client_secret), settings.AUTH0_CLIENT_SECRET),
            auth0_web_client_id=_pick(ws.auth0_web_client_id, settings.AUTH0_WEB_CLIENT_ID) or _pick(ws.auth0_m2m_client_id, settings.AUTH0_CLIENT_ID),
            auth0_web_client_secret=_pick(decrypt_secret(ws.auth0_web_client_secret), settings.AUTH0_WEB_CLIENT_SECRET) or _pick(decrypt_secret(ws.auth0_m2m_client_secret), settings.AUTH0_CLIENT_SECRET),
            auth0_audience=_pick(ws.auth0_audience, settings.AUTH0_AUDIENCE),
            auth0_mgmt_api_audience=_pick(ws.auth0_mgmt_api_audience, settings.AUTH0_MGMT_API_AUDIENCE) or f"https://{domain}/api/v2/",
            fga_api_url=_pick(ws.fga_api_url, settings.FGA_API_URL),
            fga_store_id=_pick(ws.fga_store_id, settings.FGA_STORE_ID),
            fga_model_id=_pick(ws.fga_model_id, settings.FGA_MODEL_ID),
            fga_client_id=_pick(ws.fga_client_id, settings.FGA_CLIENT_ID),
            fga_client_secret=_pick(decrypt_secret(ws.fga_client_secret), settings.FGA_CLIENT_SECRET),
            credentials_key=_pick(ws.credentials_key, settings.CREDENTIALS_KEY),
            callback_base_url=settings.CALLBACK_BASE_URL,
            frontend_url=settings.FRONTEND_URL,
        )

    # No workspace found — pure .env fallback
    return WorkspaceConfig(
        auth0_domain=settings.AUTH0_DOMAIN,
        auth0_client_id=settings.AUTH0_CLIENT_ID,
        auth0_client_secret=settings.AUTH0_CLIENT_SECRET,
        auth0_web_client_id=settings.AUTH0_WEB_CLIENT_ID or settings.AUTH0_CLIENT_ID,
        auth0_web_client_secret=settings.AUTH0_WEB_CLIENT_SECRET or settings.AUTH0_CLIENT_SECRET,
        auth0_audience=settings.AUTH0_AUDIENCE,
        auth0_mgmt_api_audience=settings.AUTH0_MGMT_API_AUDIENCE,
        fga_api_url=settings.FGA_API_URL,
        fga_store_id=settings.FGA_STORE_ID,
        fga_model_id=settings.FGA_MODEL_ID,
        fga_client_id=settings.FGA_CLIENT_ID,
        fga_client_secret=settings.FGA_CLIENT_SECRET,
        credentials_key=settings.CREDENTIALS_KEY,
        callback_base_url=settings.CALLBACK_BASE_URL,
        frontend_url=settings.FRONTEND_URL,
    )

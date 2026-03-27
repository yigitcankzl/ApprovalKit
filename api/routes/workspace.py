"""
Workspace management routes
============================
POST /api/v1/workspace/setup  — create or return existing workspace
GET  /api/v1/workspace        — get current workspace info (no secrets)
"""
import hashlib
import secrets
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from api.config import get_settings
from api.database import get_db
from api.models.workspace import Workspace
from api.services.encryption import encrypt_secret
from api.middleware.workspace import get_current_workspace


def _hash_key(key: str) -> str:
    """SHA256 hash for DB storage. One-way — original cannot be recovered."""
    return hashlib.sha256(key.encode()).hexdigest()

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
async def setup_workspace(body: WorkspaceSetupRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Create workspace with Auth0/FGA credentials stored in DB.
    If workspace exists, update its credentials.
    """
    user_sub = request.headers.get("X-User-Sub", "").strip()

    # Find workspace owned by this user (each user gets their own workspace)
    existing = None
    if user_sub:
        result = await db.execute(
            select(Workspace).where(
                Workspace.owner_auth0_sub == user_sub,
                Workspace.is_active.is_(True),
            ).limit(1)
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

    # Validate Auth0 connection — skip if using default .env credentials (no M2M provided)
    if body.auth0_m2m_client_id and body.auth0_m2m_client_secret:
        valid = await _validate_auth0(domain, m2m_id, m2m_secret)
        if not valid:
            raise HTTPException(
                status_code=400,
                detail="Could not connect to Auth0 with provided M2M credentials.",
            )

    # Generate secrets — plaintext shown to user ONCE, never stored
    api_key = secrets.token_urlsafe(32)
    hmac_secret = secrets.token_hex(32)
    ws_id = uuid.uuid4()

    # DB stores ONLY hashes — plaintext never touches the database
    workspace = Workspace(
        id=ws_id,
        name=body.name,
        auth0_tenant=domain,
        api_key=_hash_key(api_key),          # SHA256 hash only
        hmac_secret="vault",                  # Marker — real secret in Vault
        owner_auth0_sub=user_sub or None,
        auth0_domain=body.auth0_domain,
        auth0_m2m_client_id=body.auth0_m2m_client_id,
        auth0_m2m_client_secret="vault",      # Marker — real secret in Vault
        auth0_web_client_id=body.auth0_web_client_id,
        auth0_web_client_secret="vault",      # Marker — real secret in Vault
        auth0_audience=body.auth0_audience,
        auth0_mgmt_api_audience=f"https://{domain}/api/v2/" if domain else None,
        fga_api_url=body.fga_api_url,
        fga_store_id=body.fga_store_id,
        fga_model_id=body.fga_model_id,
        fga_client_id=body.fga_client_id,
        fga_client_secret="vault",            # Marker — real secret in Vault
    )
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)

    # Store ALL secrets in HashiCorp Vault — never in DB
    from api.services.vault import store_secret
    store_secret(str(ws_id), "hmac", {"hmac_secret": hmac_secret})
    store_secret(str(ws_id), "auth0", {
        "m2m_client_secret": body.auth0_m2m_client_secret or "",
        "web_client_secret": body.auth0_web_client_secret or "",
    })
    if body.fga_client_secret:
        store_secret(str(ws_id), "fga", {"client_secret": body.fga_client_secret})

    logger.info(f"Workspace created: {ws_id} — secrets stored in Vault, DB has hashes only")
    return JSONResponse(
        content={
            "workspace_id": str(ws_id),
            "name": workspace.name,
            "auth0_tenant": workspace.auth0_tenant,
            "api_key": api_key,
            "hmac_secret": hmac_secret,
            "created": True,
        },
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


@router.get("/tenant-config")
async def get_tenant_config(domain: str = "", db: AsyncSession = Depends(get_db)):
    """Public endpoint — returns Auth0 client_id for a tenant domain (no secrets).
    Used by /login page to configure Auth0Client before login.
    """
    if domain:
        result = await db.execute(
            select(Workspace).where(Workspace.auth0_domain == domain).limit(1)
        )
        ws = result.scalar_one_or_none()
        if ws and ws.auth0_web_client_id:
            return {
                "domain": ws.auth0_domain,
                "client_id": ws.auth0_web_client_id,
                "found": True,
            }

    # Fallback to default tenant from .env
    return {
        "domain": settings.AUTH0_DOMAIN,
        "client_id": settings.AUTH0_WEB_CLIENT_ID or settings.AUTH0_CLIENT_ID,
        "found": False,
    }


@router.get("/credentials")
async def get_workspace_credentials(workspace: Workspace = Depends(get_current_workspace)):
    """Returns workspace info. Secrets are shown only once at creation time."""
    return {
        "workspace_id": str(workspace.id),
        "name": workspace.name,
        "has_api_key": bool(workspace.api_key),
        "has_hmac_secret": bool(workspace.hmac_secret),
    }


@router.get("")
async def get_workspace(workspace: Workspace = Depends(get_current_workspace)):
    return {
        "workspace_id": str(workspace.id),
        "name": workspace.name,
        "auth0_tenant": workspace.auth0_tenant,
        "is_active": workspace.is_active,
        "has_auth0_credentials": bool(workspace.auth0_domain and workspace.auth0_m2m_client_id),
        "has_fga_credentials": bool(workspace.fga_store_id),
        "has_ai_api_key": bool(workspace.ai_api_key_encrypted),
        "created_at": workspace.created_at.isoformat(),
    }


# ── AI API Key Management (HashiCorp Vault → Fernet fallback) ─────────────────

from api.services.vault import store_secret, read_secret, delete_secret, is_vault_available
from api.services.encryption import decrypt_secret

_AI_KEY_SLUG = "_ai_api_key"


class AIKeyRequest(BaseModel):
    api_key: str
    provider: str = "gemini"  # gemini | groq | openrouter | mistral


SUPPORTED_PROVIDERS = {
    "gemini": {"name": "Google Gemini", "url": "https://aistudio.google.com/apikey"},
    "groq": {"name": "Groq", "url": "https://console.groq.com/keys"},
    "openrouter": {"name": "OpenRouter", "url": "https://openrouter.ai/keys"},
    "mistral": {"name": "Mistral", "url": "https://console.mistral.ai/api-keys"},
}


@router.post("/ai-key")
async def save_ai_api_key(
    body: AIKeyRequest,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Store the user's AI API key + provider. Primary: HashiCorp Vault. Fallback: Fernet in DB."""
    if not body.api_key or len(body.api_key) < 10:
        raise HTTPException(status_code=422, detail="Invalid API key")
    if body.provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=422, detail=f"Unsupported provider. Supported: {', '.join(SUPPORTED_PROVIDERS.keys())}")

    ws_id = str(workspace.id)
    stored_in_vault = store_secret(ws_id, _AI_KEY_SLUG, {"api_key": body.api_key, "provider": body.provider})

    if stored_in_vault:
        workspace.ai_api_key_encrypted = "vault"
    else:
        workspace.ai_api_key_encrypted = encrypt_secret(f"{body.provider}:{body.api_key}")

    await db.commit()
    return {"status": "saved", "has_ai_api_key": True, "provider": body.provider, "storage": "vault" if stored_in_vault else "encrypted_db"}


@router.delete("/ai-key")
async def delete_ai_api_key(
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Remove the stored AI API key from both Vault and DB."""
    ws_id = str(workspace.id)
    delete_secret(ws_id, _AI_KEY_SLUG)
    workspace.ai_api_key_encrypted = None
    await db.commit()
    return {"status": "deleted", "has_ai_api_key": False}


@router.get("/ai-key/status")
async def ai_api_key_status(
    workspace: Workspace = Depends(get_current_workspace),
):
    """Check if an AI API key is configured (never returns the key itself)."""
    has_key = bool(workspace.ai_api_key_encrypted)
    provider = None
    if has_key and workspace.ai_api_key_encrypted == "vault":
        vault_data = read_secret(str(workspace.id), _AI_KEY_SLUG)
        if vault_data:
            provider = vault_data.get("provider", "gemini")
    elif has_key:
        decrypted = decrypt_secret(workspace.ai_api_key_encrypted) or ""
        if ":" in decrypted:
            provider = decrypted.split(":", 1)[0]
        else:
            provider = "gemini"
    return {"has_ai_api_key": has_key, "provider": provider, "providers": list(SUPPORTED_PROVIDERS.keys())}

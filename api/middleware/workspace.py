"""
Per-user workspace resolution.

Dashboard API calls identify the caller by the Auth0 access token in
`X-User-Token` (preferred) or by an Authorization: Bearer header. The
token's signature is verified against the tenant JWKS and its `sub`
claim determines which workspace is returned.

The legacy `X-User-Sub` header is still accepted when no token is
present, BUT only in non-production environments, because it is
trivially spoofable. In production a missing/invalid token returns 401.
"""
import time
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException, Request
from jwt import PyJWKClient
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import get_db
from api.models.workspace import Workspace

settings = get_settings()


# JWKS clients are expensive to construct — cache one per issuer.
_jwks_clients: dict[str, PyJWKClient] = {}


def _jwks_client(domain: str) -> PyJWKClient:
    client = _jwks_clients.get(domain)
    if client is None:
        client = PyJWKClient(
            f"https://{domain}/.well-known/jwks.json",
            cache_keys=True,
            lifespan=3600,
        )
        _jwks_clients[domain] = client
    return client


def _extract_bearer(request: Request) -> str | None:
    # Prefer explicit X-User-Token header the frontend already sends.
    token = request.headers.get("X-User-Token", "").strip()
    if token:
        return token
    auth = request.headers.get("Authorization", "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return None


def _verify_auth0_token(token: str, domain: str) -> dict[str, Any] | None:
    """Verify a JWT against the tenant JWKS. Returns decoded claims or None."""
    try:
        signing_key = _jwks_client(domain).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=f"https://{domain}/",
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iss": True,
                # audience varies (api / userinfo / management) — don't enforce here
                "verify_aud": False,
            },
            leeway=30,
        )
        return claims
    except jwt.PyJWTError as e:
        logger.warning(f"JWT verification failed: {type(e).__name__}: {e}")
        return None
    except Exception as e:
        logger.warning(f"JWT verification error: {type(e).__name__}: {e}")
        return None


def _jwt_enforcement_enabled() -> bool:
    """
    JWT-based auth is only enforced when we can actually verify a token:
    production mode AND AUTH0_DOMAIN configured. Without a domain we have
    nothing to fetch JWKS from, so fall back to header-based identity.
    """
    return settings.ENVIRONMENT == "production" and bool(settings.AUTH0_DOMAIN)


async def _resolve_sub(request: Request) -> str | None:
    """Return the authenticated Auth0 sub for this request, or None."""
    token = _extract_bearer(request)
    if token and settings.AUTH0_DOMAIN:
        claims = _verify_auth0_token(token, settings.AUTH0_DOMAIN)
        if claims:
            return claims.get("sub")
        # Token present but invalid: don't silently fall back to a
        # spoofable X-User-Sub header.
        return None

    # No valid token. Honour X-User-Sub only when JWT enforcement is off
    # (dev/test or Auth0 not configured at all).
    if not _jwt_enforcement_enabled():
        return request.headers.get("X-User-Sub", "").strip() or None
    return None


async def get_current_workspace(request: Request, db: AsyncSession = Depends(get_db)) -> Workspace:
    """
    Resolve workspace for the current user.

    Production path: verify the Auth0 access token, look up the workspace
    owned by `sub`. If there's no workspace for that user → 404 so they
    can complete setup.

    Dev/test fallback (non-production only): accept an X-User-Sub header
    OR fall back to the first active workspace (for SDK/API calls).
    """
    user_sub = await _resolve_sub(request)
    logger.debug(f"Workspace resolve: sub={user_sub!r} path={request.url.path}")

    if user_sub:
        result = await db.execute(
            select(Workspace).where(
                Workspace.owner_auth0_sub == user_sub,
                Workspace.is_active.is_(True),
            ).limit(1)
        )
        ws = result.scalar_one_or_none()
        if ws:
            return ws
        raise HTTPException(
            status_code=404,
            detail="No workspace found for your account. Complete setup at /settings first.",
        )

    # No verified identity.
    if _jwt_enforcement_enabled():
        raise HTTPException(
            status_code=401,
            detail="Authentication required: provide a valid Auth0 access token in X-User-Token.",
        )

    # Fallback path (non-prod OR Auth0 not configured): first active workspace.
    result = await db.execute(
        select(Workspace).where(Workspace.is_active.is_(True)).limit(1)
    )
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="No workspace configured. Complete setup first.")
    return ws

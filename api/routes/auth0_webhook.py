"""
Auth0 Actions Webhook Receiver
===============================
Receives callbacks from Auth0 Actions (post-login, credentials-exchange)
and performs corresponding actions:

- post_login_fga_sync: Write FGA tuples to sync user roles automatically
- token_exchange_audit: Log Token Vault exchanges to the audit trail

All webhooks are verified via HMAC-SHA256 signature.
"""
import hashlib
import hmac
import time

import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException, Request
from loguru import logger
from pydantic import BaseModel

from api.config import get_settings
from api.services.fga import fga_client

router = APIRouter(prefix="/api/v1", tags=["auth0-webhook"])
settings = get_settings()

_WEBHOOK_TIMESTAMP_TOLERANCE = 300  # 5 minutes
_WEBHOOK_NONCE_TTL = 600  # nonce memory window


async def _nonce_seen(nonce: str) -> bool:
    """Return True if this nonce was already consumed (replay)."""
    if not nonce:
        return False
    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            # SETNX: succeeds only if key is new.
            ok = await r.set(f"auth0_webhook_nonce:{nonce}", "1", ex=_WEBHOOK_NONCE_TTL, nx=True)
        finally:
            await r.aclose()
        return not ok
    except Exception as e:
        # Fail closed: if Redis is down we cannot guarantee replay safety.
        logger.error(f"Auth0 webhook nonce check failed: {e}")
        return True


class PostLoginPayload(BaseModel):
    event_type: str
    user_id: str
    email: str | None = None
    role: str
    workspace_id: str
    timestamp: str
    connection: str | None = None
    ip: str | None = None


class TokenExchangePayload(BaseModel):
    event_type: str
    client_id: str
    client_name: str | None = None
    audience: str | None = None
    scopes: str | None = None
    timestamp: str
    ip: str | None = None


def _verify_signature(body: bytes, signature: str, timestamp: str) -> bool:
    """
    Verify HMAC-SHA256 signature from Auth0 Action.

    The signature is computed over `{timestamp}.{body}` to bind the
    timestamp into the MAC; an attacker cannot modify the timestamp
    to keep a replayed request "fresh".
    """
    secret = settings.HMAC_SECRET
    if not secret:
        return False
    msg = timestamp.encode() + b"." + body
    expected = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/auth0-webhook")
async def auth0_webhook(request: Request):
    """
    Receives webhooks from Auth0 Actions.

    Headers:
      X-Auth0-Signature: HMAC-SHA256 hex digest
      X-Auth0-Action: "post-login" | "credentials-exchange"
    """
    signature = request.headers.get("X-Auth0-Signature", "")
    action_type = request.headers.get("X-Auth0-Action", "")
    timestamp = request.headers.get("X-Auth0-Timestamp", "")
    nonce = request.headers.get("X-Auth0-Nonce", "")
    body = await request.body()

    # Require timestamp + nonce + freshness window.
    try:
        ts_int = int(timestamp)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Missing or invalid X-Auth0-Timestamp")
    if abs(int(time.time()) - ts_int) > _WEBHOOK_TIMESTAMP_TOLERANCE:
        raise HTTPException(status_code=401, detail="Webhook timestamp outside tolerance window")
    if not nonce or len(nonce) < 8:
        raise HTTPException(status_code=401, detail="Missing X-Auth0-Nonce")

    if not _verify_signature(body, signature, timestamp):
        logger.warning("Auth0 webhook: invalid signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    if await _nonce_seen(nonce):
        logger.warning(f"Auth0 webhook: replayed nonce {nonce[:12]}...")
        raise HTTPException(status_code=401, detail="Replayed or reused nonce")

    data = await request.json()

    if action_type == "post-login":
        return await _handle_post_login(data)
    elif action_type == "credentials-exchange":
        return await _handle_credentials_exchange(data)
    else:
        logger.warning(f"Auth0 webhook: unknown action type '{action_type}'")
        raise HTTPException(status_code=400, detail=f"Unknown action type: {action_type}")


async def _handle_post_login(data: dict):
    """Sync user role to FGA after login."""
    payload = PostLoginPayload(**data)

    # Write FGA tuple: user:{user_id} -> {role} -> workspace:{workspace_id}
    success = await fga_client.write_tuple(
        user=f"user:{payload.user_id}",
        relation=payload.role,
        obj=f"workspace:{payload.workspace_id}",
    )

    logger.info(
        f"Auth0 post-login FGA sync: user={payload.user_id} role={payload.role} "
        f"workspace={payload.workspace_id} success={success}"
    )

    return {
        "status": "ok",
        "action": "fga_sync",
        "user_id": payload.user_id,
        "role": payload.role,
        "fga_write": success,
    }


async def _handle_credentials_exchange(data: dict):
    """Log Token Vault exchange to audit trail."""
    payload = TokenExchangePayload(**data)

    logger.info(
        f"Auth0 credentials exchange audit: client={payload.client_name} "
        f"audience={payload.audience} scopes={payload.scopes}"
    )

    return {
        "status": "ok",
        "action": "audit_logged",
        "client_id": payload.client_id,
        "timestamp": payload.timestamp,
    }

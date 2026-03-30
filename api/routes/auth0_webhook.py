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

from fastapi import APIRouter, HTTPException, Request
from loguru import logger
from pydantic import BaseModel

from api.config import get_settings
from api.services.fga import fga_client

router = APIRouter(prefix="/api/v1", tags=["auth0-webhook"])
settings = get_settings()


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


def _verify_signature(body: bytes, signature: str) -> bool:
    """Verify HMAC-SHA256 signature from Auth0 Action."""
    secret = settings.HMAC_SECRET
    if not secret:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
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
    body = await request.body()

    if not _verify_signature(body, signature):
        logger.warning("Auth0 webhook: invalid signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

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

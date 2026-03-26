import hashlib
import hmac
import time

from fastapi import HTTPException, Request, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.workspace import Workspace
from api.models.agent import RegisteredAgent


async def verify_hmac_signature(request: Request, db: AsyncSession = Depends(get_db)) -> Workspace:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    api_key = auth_header.removeprefix("Bearer ").strip()

    signature_header = request.headers.get("X-Signature")
    if not signature_header or not signature_header.startswith("hmac-sha256="):
        raise HTTPException(status_code=401, detail="Missing or invalid X-Signature header")

    sig_value = signature_header.removeprefix("hmac-sha256=")
    parts = sig_value.split(".", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=401, detail="Invalid signature format")

    timestamp_str, provided_hash = parts

    try:
        timestamp = int(timestamp_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid timestamp in signature")

    now = int(time.time())
    if abs(now - timestamp) > 300:
        raise HTTPException(status_code=401, detail="Request timestamp too old (replay attack prevention)")

    # Try per-agent API key first (ak_* format)
    workspace = None
    agent = None
    if api_key.startswith("ak_"):
        result = await db.execute(
            select(RegisteredAgent).where(
                RegisteredAgent.api_key == api_key,
                RegisteredAgent.is_active.is_(True),
            )
        )
        agent = result.scalar_one_or_none()
        if agent:
            ws_result = await db.execute(
                select(Workspace).where(Workspace.id == agent.workspace_id, Workspace.is_active.is_(True))
            )
            workspace = ws_result.scalar_one_or_none()

    # Fall back to workspace API key
    if not workspace:
        result = await db.execute(select(Workspace).where(Workspace.api_key == api_key, Workspace.is_active.is_(True)))
        workspace = result.scalar_one_or_none()

    if not workspace:
        raise HTTPException(status_code=401, detail="Invalid API key")

    body = await request.body()
    try:
        body_str = body.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Request body must be valid UTF-8")
    message = f"{timestamp_str}.{body_str}"

    # Per-agent signing: use hmac_secret:agent_api_key for isolation
    sign_key = workspace.hmac_secret
    if agent:
        sign_key = f"{workspace.hmac_secret}:{agent.api_key}"

    expected_hash = hmac.new(
        sign_key.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, provided_hash):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    return workspace

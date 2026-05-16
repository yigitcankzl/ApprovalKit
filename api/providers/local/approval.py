"""
Local approval channel for development and self-hosted deployments.

This implementation does **not** dispatch real push notifications. It
mimics the CIBA lifecycle entirely via Redis:

* ``initiate`` stores a pending record keyed by a randomly generated
  ``auth_req_id`` and (optionally) logs an "approval URL" that points
  at the local dashboard. The URL/handle is the only thing approvers
  need.
* ``poll`` reads back the stored record and waits for an approve/reject
  decision (written via the dashboard / `/local-approvals/:id/decide`
  endpoint).

The intent is to let people run ApprovalKit end-to-end without any
Auth0 account. For real production deployments, swap in the Auth0 CIBA
channel via `APPROVAL_PROVIDER=auth0`.
"""
from __future__ import annotations

import asyncio
import json
import secrets
import time
from typing import Any

from loguru import logger

from api.providers.base import (
    ApprovalChannel,
    ApprovalRequest,
    ApprovalResponse,
    ApprovalStatus,
)
from api.services.redis_pool import get_redis


_KEY_PREFIX = "approvalkit:local-approval:"
_DEFAULT_TTL = 600  # 10 minutes
_POLL_INTERVAL = 1.0  # seconds


def _key(handle: str) -> str:
    return f"{_KEY_PREFIX}{handle}"


class LocalApprovalChannel(ApprovalChannel):
    name = "local"

    def __init__(self, *, dashboard_url: str = "", auto_approve: bool = False):
        """
        Args:
            dashboard_url: Optional base URL used when building the log
                message that surfaces the approval handle to operators.
            auto_approve: When True, every request is immediately marked
                approved — useful for CI/integration tests. Never enable
                in production.
        """
        self.dashboard_url = dashboard_url.rstrip("/")
        self.auto_approve = auto_approve

    async def initiate(self, request: ApprovalRequest) -> str:
        handle = secrets.token_urlsafe(24)
        record = {
            "user_id": request.user_id,
            "binding_message": request.binding_message,
            "scope": request.scope,
            "job_id": request.job_id,
            "created_at": int(time.time()),
            "status": "approved" if self.auto_approve else "pending",
        }
        redis = get_redis()
        await redis.setex(_key(handle), _DEFAULT_TTL, json.dumps(record))
        if self.dashboard_url and not self.auto_approve:
            logger.info(
                "Local approval requested — open "
                f"{self.dashboard_url}/local-approvals/{handle} to decide "
                f"(user={request.user_id}, msg={request.binding_message!r})"
            )
        elif self.auto_approve:
            logger.info(f"Local approval auto-approved: {request.binding_message!r}")
        return handle

    async def poll(
        self, handle: str, *, timeout: int, job_id: str = "",
    ) -> ApprovalResponse:
        redis = get_redis()
        deadline = time.time() + timeout
        while time.time() < deadline:
            raw = await redis.get(_key(handle))
            if raw is None:
                return ApprovalResponse(
                    status=ApprovalStatus.TIMEOUT,
                    source="local",
                    error="handle expired",
                )
            try:
                record = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return ApprovalResponse(
                    status=ApprovalStatus.ERROR,
                    source="local",
                    error="corrupt record",
                )
            status = record.get("status", "pending")
            if status == "approved":
                return ApprovalResponse(
                    status=ApprovalStatus.APPROVED, source="local",
                )
            if status == "rejected":
                return ApprovalResponse(
                    status=ApprovalStatus.REJECTED, source="local",
                )
            await asyncio.sleep(_POLL_INTERVAL)
        return ApprovalResponse(status=ApprovalStatus.TIMEOUT, source="local")


async def record_decision(handle: str, *, approved: bool) -> bool:
    """Record an approve/reject decision for a local-channel handle.

    Returns True if a pending record was found and updated, False
    otherwise. Routes can call this from a simple local dashboard or
    curl-friendly endpoint.
    """
    redis = get_redis()
    raw = await redis.get(_key(handle))
    if raw is None:
        return False
    try:
        record = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return False
    record["status"] = "approved" if approved else "rejected"
    record["decided_at"] = int(time.time())
    await redis.setex(_key(handle), _DEFAULT_TTL, json.dumps(record))
    return True


async def get_pending(handle: str) -> dict[str, Any] | None:
    """Inspect a pending local-approval record (for the dashboard)."""
    redis = get_redis()
    raw = await redis.get(_key(handle))
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None

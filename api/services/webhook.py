"""Webhook notification service — fire-and-forget HTTP callbacks on approval events."""

import hashlib
import hmac
import json
import time

import httpx
from loguru import logger

from api.constants import WEBHOOK_TIMEOUT_SECONDS, WEBHOOK_MAX_RETRIES


async def send_webhook(
    url: str,
    event: str,
    payload: dict,
    secret: str | None = None,
) -> bool:
    """POST a signed JSON payload to the webhook URL.

    Headers include:
    - X-ApprovalKit-Event: event name (e.g. "job.approved")
    - X-ApprovalKit-Signature: HMAC-SHA256 if secret provided
    - X-ApprovalKit-Timestamp: Unix timestamp

    Returns True if delivered (2xx), False otherwise.
    """
    body = json.dumps(payload, default=str)
    ts = str(int(time.time()))

    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "X-ApprovalKit-Event": event,
        "X-ApprovalKit-Timestamp": ts,
    }

    if secret:
        sig = hmac.new(
            secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256,
        ).hexdigest()
        headers["X-ApprovalKit-Signature"] = f"sha256={sig}"

    for attempt in range(WEBHOOK_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT_SECONDS) as client:
                r = await client.post(url, content=body, headers=headers)
                if 200 <= r.status_code < 300:
                    logger.info(f"Webhook delivered: {event} → {url} ({r.status_code})")
                    return True
                logger.warning(f"Webhook {url} returned {r.status_code} (attempt {attempt + 1})")
        except Exception as e:
            logger.warning(f"Webhook {url} failed (attempt {attempt + 1}): {e}")

    logger.error(f"Webhook exhausted retries: {event} → {url}")
    return False


WEBHOOK_EVENTS = {
    "job.approved",
    "job.rejected",
    "job.timeout",
    "job.escalated",
    "job.pre_approved",
    "job.scope_creep",
    "job.budget_exceeded",
}

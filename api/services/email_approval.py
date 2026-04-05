"""
Email Approval Service
=======================
Generates secure, time-limited approval URLs that allow approvers to
approve or reject requests via email — no Auth0 Guardian app required.

The approval link contains a signed JWT with the job ID and expiry.
When clicked, it leads to a lightweight approval page that calls the
existing `submit_web_decision` endpoint.

This adds Auth0 Passwordless as an additional approval channel alongside
CIBA push notifications, expanding accessibility for approvers who
don't have the Guardian app installed.
"""
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta

import httpx
from loguru import logger

from api.config import get_settings
from api.services.redis_pool import get_redis

settings = get_settings()


def _token_fingerprint(token: str) -> str:
    """SHA-256 of token — used as Redis key so raw tokens never hit Redis."""
    return hashlib.sha256(token.encode()).hexdigest()


async def consume_approval_token(token: str) -> dict | None:
    """
    Atomically verify + consume a single-use approval token.

    Returns the decoded claims on success, or None if the token is
    invalid, expired, or already used. Uses Redis SETNX so concurrent
    callers cannot both succeed.
    """
    claims = verify_approval_token(token)
    if not claims:
        return None

    key = f"used_token:{_token_fingerprint(token)}"
    ttl = max(1, int(claims["expiry"]) - int(time.time()) + 60)
    try:
        r = get_redis()
        # SET NX: only succeeds if the key does not exist
        set_ok = await r.set(key, "1", ex=ttl, nx=True)
    except Exception as e:
        # Redis unavailable — fail closed rather than allow replay
        logger.error(f"Approval token replay check failed (Redis): {e}")
        return None

    if not set_ok:
        logger.warning(f"Approval token replay attempt: fingerprint={key[:20]}...")
        return None
    return claims


def _generate_approval_token(job_id: str, approver_email: str, expires_in: int = 3600) -> str:
    """
    Generate a signed approval token (HMAC-SHA256).

    Token format: base64url({job_id}:{approver_email}:{expiry_ts}):signature
    This avoids needing a JWT library — simple, auditable, and secure.
    """
    expiry_ts = int(time.time()) + expires_in
    payload = f"{job_id}:{approver_email}:{expiry_ts}"
    signature = hmac.new(
        settings.HMAC_SECRET.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}:{signature}"


def verify_approval_token(token: str) -> dict | None:
    """
    Verify and decode an approval token.

    Returns {"job_id": ..., "approver_email": ..., "expiry": ...} or None if invalid.
    """
    parts = token.rsplit(":", 1)
    if len(parts) != 2:
        return None

    payload, signature = parts
    expected = hmac.new(
        settings.HMAC_SECRET.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        return None

    segments = payload.split(":")
    if len(segments) != 3:
        return None

    job_id, approver_email, expiry_ts = segments
    if int(expiry_ts) < int(time.time()):
        return None

    return {
        "job_id": job_id,
        "approver_email": approver_email,
        "expiry": int(expiry_ts),
    }


def generate_approval_url(job_id: str, approver_email: str, expires_in: int = 3600) -> str:
    """Generate a full approval URL for the frontend."""
    token = _generate_approval_token(job_id, approver_email, expires_in)
    frontend_url = settings.FRONTEND_URL.rstrip("/")
    return f"{frontend_url}/approve/{token}"


async def send_approval_email(
    approver_email: str,
    approver_name: str,
    job_id: str,
    connection: str,
    action: str,
    binding_message: str,
    timeout_seconds: int = 3600,
) -> bool:
    """
    Send an approval email using Auth0's Management API.

    Falls back to logging the approval URL if email sending is not configured.
    This uses Auth0's built-in email infrastructure — no third-party email
    service needed.
    """
    approval_url = generate_approval_url(job_id, approver_email, timeout_seconds)
    reject_url = f"{approval_url}&decision=reject"

    logger.info(
        f"Email approval generated: job={job_id} approver={approver_email} "
        f"connection={connection} action={action}"
    )
    logger.info(f"Approval URL: {approval_url}")

    # Try Auth0 Management API to send email via passwordless
    if settings.AUTH0_DOMAIN and settings.AUTH0_CLIENT_ID and settings.AUTH0_CLIENT_SECRET:
        try:
            # Get M2M token
            async with httpx.AsyncClient(timeout=10) as client:
                token_resp = await client.post(
                    f"https://{settings.AUTH0_DOMAIN}/oauth/token",
                    json={
                        "client_id": settings.AUTH0_CLIENT_ID,
                        "client_secret": settings.AUTH0_CLIENT_SECRET,
                        "audience": f"https://{settings.AUTH0_DOMAIN}/api/v2/",
                        "grant_type": "client_credentials",
                    },
                )
                if token_resp.status_code != 200:
                    logger.warning(f"Auth0 token for email failed: {token_resp.status_code}")
                    return False

                mgmt_token = token_resp.json()["access_token"]

                # Send passwordless email with magic link
                email_resp = await client.post(
                    f"https://{settings.AUTH0_DOMAIN}/passwordless/start",
                    json={
                        "client_id": settings.AUTH0_WEB_CLIENT_ID or settings.AUTH0_CLIENT_ID,
                        "client_secret": settings.AUTH0_WEB_CLIENT_SECRET or settings.AUTH0_CLIENT_SECRET,
                        "connection": "email",
                        "email": approver_email,
                        "send": "link",
                        "authParams": {
                            "redirect_uri": approval_url,
                            "scope": "openid email",
                        },
                    },
                )
                if email_resp.status_code == 200:
                    logger.info(f"Auth0 passwordless email sent to {approver_email}")
                    return True
                else:
                    logger.warning(f"Auth0 passwordless email failed: {email_resp.status_code} {email_resp.text[:200]}")

        except Exception as e:
            logger.warning(f"Auth0 email error: {e}")
            return False

    # No Auth0 credentials configured — email wasn't sent, but the URL
    # is still generated and logged so the approver can reach it via
    # the dashboard. Surface this to the caller as a failed send.
    return False

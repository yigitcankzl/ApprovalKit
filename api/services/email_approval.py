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

settings = get_settings()


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
                    return True  # URL still generated

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

    # Always return True — the URL is generated even if email delivery fails
    # The approver can still use the dashboard to approve
    return True

"""Webhook notification service — fire-and-forget HTTP callbacks on approval events."""

import asyncio
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
        if attempt < WEBHOOK_MAX_RETRIES - 1:
            await asyncio.sleep(min(2 ** attempt, 10))

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


async def notify_slack(
    webhook_url: str,
    title: str,
    message: str,
    color: str = "#2196F3",
    fields: list[dict] | None = None,
) -> bool:
    """Send a Slack notification via incoming webhook.

    ``webhook_url`` is a Slack Incoming Webhook URL
    (https://hooks.slack.com/services/T.../B.../xxx).
    """
    attachment = {
        "color": color,
        "title": title,
        "text": message,
        "ts": int(time.time()),
    }
    if fields:
        attachment["fields"] = fields

    from api.utils import assert_safe_outbound_url_async, UnsafeURLError
    try:
        await assert_safe_outbound_url_async(webhook_url)
    except UnsafeURLError as e:
        logger.warning(f"Slack webhook URL rejected (SSRF guard): {e}")
        return False

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            r = await client.post(webhook_url, json={"attachments": [attachment]})
            if r.status_code == 200:
                logger.info(f"Slack notification sent: {title}")
                return True
            logger.warning(f"Slack webhook returned {r.status_code}: {r.text[:100]}")
    except Exception as e:
        logger.warning(f"Slack notification failed: {e}")
    return False


async def notify_email(
    to: str,
    subject: str,
    body: str,
    smtp_host: str = "localhost",
    smtp_port: int = 587,
    smtp_user: str = "",
    smtp_pass: str = "",
    from_addr: str = "approvalkit@noreply.local",
) -> bool:
    """Send an email notification via SMTP.

    For production, configure with a real SMTP provider (SendGrid, SES, etc.).
    Falls back to logging if SMTP is not configured.
    """
    if not smtp_user:
        logger.info(f"Email notification (no SMTP configured): to={to} subject={subject}")
        return True  # Log-only mode

    try:
        import smtplib
        from email.mime.text import MIMEText

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        logger.info(f"Email sent: {subject} → {to}")
        return True
    except Exception as e:
        logger.warning(f"Email notification failed: {e}")
        return False


async def notify_approval_requested(
    job_connection: str,
    job_action: str,
    binding_message: str,
    approver_name: str,
    slack_webhook_url: str | None = None,
    email_to: str | None = None,
):
    """Send approval notification via available channels (Slack + email)."""
    title = f"Approval Required: {job_connection}/{job_action}"

    if slack_webhook_url:
        await notify_slack(
            webhook_url=slack_webhook_url,
            title=title,
            message=binding_message,
            color="#FF9800",
            fields=[
                {"title": "Approver", "value": approver_name, "short": True},
                {"title": "Action", "value": f"{job_connection}/{job_action}", "short": True},
            ],
        )

    if email_to:
        await notify_email(
            to=email_to,
            subject=f"[ApprovalKit] {title}",
            body=f"An approval is waiting for you.\n\n{binding_message}\n\nApprover: {approver_name}\nAction: {job_connection}/{job_action}\n\nLog in to the dashboard to approve or reject.",
        )


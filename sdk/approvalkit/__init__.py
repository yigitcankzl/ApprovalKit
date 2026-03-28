"""
ApprovalKit Python SDK
======================
Add human approval to any function with a single decorator.
After approval, Token Vault executes the action server-side —
the agent never holds credentials.

Usage:
    from approvalkit_sdk import ApprovalKit, ApprovalDenied

    kit = ApprovalKit(
        base_url="http://localhost:8000",
        api_key="your-api-key",
        hmac_secret="your-hmac-secret",
        user_id="my-agent",
    )

    # Decorator — fn() body is never called; Token Vault executes the action
    @kit.requires_approval(connection="stripe-prod", action="charge")
    def charge_customer(amount: int, customer: str):
        pass  # body ignored — Token Vault handles execution after approval

    result = charge_customer(amount=150, customer="alice@example.com")
    # result = {"status": "approved", "final_params": {...}}

    # Inline gate
    result = kit.gate("stripe-prod", "charge", {"amount": 150, "customer": "alice@example.com"})
    # result = {"status": "approved", "final_params": {...}}

    # Async decorator
    @kit.async_requires_approval(connection="github-main", action="deploy")
    async def deploy(env: str, branch: str):
        pass

    # Async gate
    result = await kit.async_gate("github-main", "deploy", {"env": "production", "branch": "main"})
"""

import asyncio
import functools
import hashlib
import hmac
import logging
import random
import inspect
import json
import time
import uuid
from typing import Callable

import requests

_log = logging.getLogger("approvalkit")


class ApprovalDenied(Exception):
    """Raised when an approval request is rejected, timed out, or blocked."""
    def __init__(self, status: str, job_id: str | None = None):
        self.status = status
        self.job_id = job_id
        super().__init__(f"Approval {status}" + (f" (job={job_id})" if job_id else ""))


class ApprovalKit:
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str = "",
        hmac_secret: str = "",
        user_id: str = "agent",
        poll_interval: int = 3,
        timeout: int = 300,
        http_timeout: int = 10,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.hmac_secret = hmac_secret
        self.user_id = user_id
        self.poll_interval = poll_interval
        self.timeout = timeout
        self.http_timeout = http_timeout


    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sign(self, body: str) -> tuple[str, str]:
        """
        HMAC-SHA256 request signing.
        Uses agent-specific api_key as part of the signing material
        when available, providing per-agent signature isolation.
        """
        ts = str(int(time.time()))
        # Per-agent HMAC key composition: "hmac_secret:agent_api_key"
        # This MUST match the backend's verify_hmac_signature in api/middleware/auth.py:72-75
        sign_key = self.hmac_secret
        if self.api_key:
            sign_key = f"{self.hmac_secret}:{self.api_key}"
        sig = hmac.new(
            sign_key.encode(),
            f"{ts}.{body}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return ts, sig

    def _headers(self, ts: str, sig: str) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-Signature": f"hmac-sha256={ts}.{sig}",
            "Content-Type": "application/json",
        }

    def _validate_inputs(self, connection: str, action: str, params: dict):
        if not connection or not isinstance(connection, str):
            raise ValueError("connection must be a non-empty string (e.g. 'stripe-prod')")
        if not action or not isinstance(action, str):
            raise ValueError("action must be a non-empty string (e.g. 'charge')")
        if not isinstance(params, dict):
            raise TypeError(f"params must be a dict, got {type(params).__name__}")

    def _request_approval(self, connection: str, action: str, params: dict) -> dict:
        payload = {
            "connection": connection,
            "action": action,
            "params": params,
            "user_id": self.user_id,
            "idempotency_key": str(uuid.uuid4()),
        }
        body = json.dumps(payload, separators=(",", ":"))
        ts, sig = self._sign(body)

        r = requests.post(
            f"{self.base_url}/api/v1/request",
            data=body,
            headers=self._headers(ts, sig),
            timeout=self.http_timeout,
        )

        if r.status_code == 200:
            return {"status": "pre_approved"}
        if r.status_code == 202:
            return {"status": "pending", "job_id": r.json()["job_id"]}
        if r.status_code == 403:
            return {"status": "blocked"}

        r.raise_for_status()
        return {}

    def _poll(self, job_id: str) -> tuple[str, dict]:
        """Poll until terminal status. Returns (status, full_response_data)."""
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            ts = str(int(time.time()))
            sig = hmac.new(
                self.hmac_secret.encode(),
                f"{ts}.".encode(),
                hashlib.sha256,
            ).hexdigest()
            r = requests.get(
                f"{self.base_url}/api/v1/status/{job_id}",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-Signature": f"hmac-sha256={ts}.{sig}",
                },
                timeout=self.http_timeout,
            )
            data = r.json()
            status = data.get("status", "pending")
            if status in ("approved", "rejected", "timeout", "blocked"):
                return status, data
            time.sleep(self.poll_interval + random.uniform(0, 1))
        return "timeout", {}

    def _resolve_params(self, fn, params_fn, args, kwargs) -> dict:
        if params_fn:
            return params_fn(*args, **kwargs)
        sig = inspect.signature(fn)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        return dict(bound.arguments)

    def _wait_for_approval(self, connection: str, action: str, params: dict) -> dict:
        """
        Submit request and wait for approval.
        Returns {"status": "approved"/"pre_approved", "final_params": {...}}
        Raises ApprovalDenied on rejection/timeout/block.
        """
        self._validate_inputs(connection, action, params)
        _log.info(f" {connection}/{action}")
        _log.info(f"params: {json.dumps(params)}")

        result = self._request_approval(connection, action, params)

        if result["status"] == "pre_approved":
            _log.info(" Pre-approved — Token Vault executing.")
            return {"status": "pre_approved", "final_params": params}

        if result["status"] == "blocked":
            _log.info(" Blocked by policy.")
            raise ApprovalDenied("blocked")

        job_id = result["job_id"]
        _log.info(f"Pending (job={job_id}) — push notification sent.")

        status, data = self._poll(job_id)

        if status == "approved":
            final_params = data.get("final_params") or params
            _log.info(" Approved — Token Vault executed server-side.")
            return {"status": "approved", "final_params": final_params}

        _log.info(f"{status} — action NOT executed.")
        raise ApprovalDenied(status, job_id=job_id)

    # ------------------------------------------------------------------
    # Sync public API
    # ------------------------------------------------------------------

    def requires_approval(
        self,
        connection: str,
        action: str,
        params_fn: Callable[..., dict] | None = None,
    ):
        """
        Decorator — gates the wrapped function behind a human approval.
        fn() body is NEVER called. After approval, Token Vault executes
        the action server-side using stored credentials.

        Returns {"status": "approved", "final_params": {...}}.

        params_fn: optional callable to build the params dict from fn args.
                   If omitted, all fn arguments are sent as params.
        """
        def decorator(fn: Callable) -> Callable:
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                params = self._resolve_params(fn, params_fn, args, kwargs)
                return self._wait_for_approval(connection, action, params)
            return wrapper
        return decorator

    def gate(self, connection: str, action: str, params: dict) -> dict:
        """
        Inline approval gate — blocks until approved or raises ApprovalDenied.
        Token Vault executes the action server-side after approval.

        Returns {"status": "approved", "final_params": {...}}.
        final_params may differ from params if the approver modified them.
        """
        return self._wait_for_approval(connection, action, params)

    # ------------------------------------------------------------------
    # Async public API
    # ------------------------------------------------------------------

    def async_requires_approval(
        self,
        connection: str,
        action: str,
        params_fn: Callable[..., dict] | None = None,
    ):
        """
        Async version of requires_approval.
        HTTP calls run in a thread pool — event loop is not blocked.
        fn() body is NEVER called.
        """
        def decorator(fn: Callable) -> Callable:
            @functools.wraps(fn)
            async def wrapper(*args, **kwargs):
                params = self._resolve_params(fn, params_fn, args, kwargs)
                return await asyncio.to_thread(
                    self._wait_for_approval, connection, action, params
                )
            return wrapper
        return decorator

    async def async_gate(self, connection: str, action: str, params: dict) -> dict:
        """
        Async version of gate — awaitable, non-blocking for the event loop.
        Token Vault executes the action server-side after approval.
        """
        return await asyncio.to_thread(self._wait_for_approval, connection, action, params)

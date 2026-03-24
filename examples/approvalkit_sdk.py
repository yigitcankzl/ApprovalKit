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
import inspect
import json
import time
import uuid
from typing import Callable

import requests


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
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.hmac_secret = hmac_secret
        self.user_id = user_id
        self.poll_interval = poll_interval
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sign(self, body: str) -> tuple[str, str]:
        ts = str(int(time.time()))
        sig = hmac.new(
            self.hmac_secret.encode(),
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
            timeout=10,
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
                timeout=10,
            )
            data = r.json()
            status = data.get("status", "pending")
            if status in ("approved", "rejected", "timeout", "blocked"):
                return status, data
            time.sleep(self.poll_interval)
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
        print(f"\n[ApprovalKit] {connection}/{action}")
        print(f"             params: {json.dumps(params)}")

        result = self._request_approval(connection, action, params)

        if result["status"] == "pre_approved":
            print("[ApprovalKit] Pre-approved — Token Vault executing.")
            return {"status": "pre_approved", "final_params": params}

        if result["status"] == "blocked":
            print("[ApprovalKit] Blocked by policy.")
            raise ApprovalDenied("blocked")

        job_id = result["job_id"]
        print(f"[ApprovalKit] Pending (job={job_id}) — push notification sent.")

        status, data = self._poll(job_id)

        if status == "approved":
            final_params = data.get("final_params") or params
            print("[ApprovalKit] Approved — Token Vault executed server-side.")
            return {"status": "approved", "final_params": final_params}

        print(f"[ApprovalKit] {status} — action NOT executed.")
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

"""
ApprovalKit Python SDK
======================
Add human approval to any function with a single decorator.

Usage:
    from approvalkit_sdk import ApprovalKit, ApprovalDenied

    kit = ApprovalKit(
        base_url="http://localhost:8000",
        api_key="your-api-key",
        hmac_secret="your-hmac-secret",
        user_id="my-agent",           # any string — no auth0| prefix required
    )

    # Sync decorator — fn() runs locally after approval
    @kit.requires_approval(connection="stripe-prod", action="charge")
    def charge_customer(amount: int, customer: str):
        stripe.charge(amount=amount, customer=customer)

    # Sync decorator — Token Vault executes server-side, fn() is NOT called
    @kit.requires_approval(connection="stripe-prod", action="charge", execute_fn=False)
    def charge_customer(amount: int, customer: str):
        pass  # body is ignored; server handles execution via Token Vault

    # Async decorator
    @kit.async_requires_approval(connection="stripe-prod", action="charge")
    async def charge_customer(amount: int, customer: str):
        await stripe.charge_async(amount=amount, customer=customer)

    # Inline gate (sync)
    final_params = kit.gate("stripe-prod", "charge", {"amount": 100, "customer": "..."})
    stripe.charge(**final_params)   # use final_params — approver may have modified them

    # Inline gate (async)
    final_params = await kit.async_gate("stripe-prod", "charge", {"amount": 100})
"""

import asyncio
import functools
import hashlib
import hmac
import inspect
import json
import time
import uuid
from typing import Any, Callable

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
        if r.status_code == 403:
            return {"status": "blocked"}
        if r.status_code == 202:
            return {"status": "pending", "job_id": r.json()["job_id"]}

        r.raise_for_status()
        return {}

    def _poll(self, job_id: str) -> tuple[str, dict]:
        """Poll until terminal status. Returns (status, full_response_data)."""
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            # GET requests have empty body — sign empty string after the dot
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

    def _resolve(self, fn, params_fn, args, kwargs):
        """Build the params dict from function args."""
        if params_fn:
            return params_fn(*args, **kwargs)
        sig = inspect.signature(fn)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        return dict(bound.arguments)

    # ------------------------------------------------------------------
    # Sync public API
    # ------------------------------------------------------------------

    def requires_approval(
        self,
        connection: str,
        action: str,
        params_fn: Callable[..., dict] | None = None,
        execute_fn: bool = True,
    ):
        """
        Decorator — gates the wrapped function behind a human approval.

        execute_fn=True  (default): fn() runs locally after approval.
                                    Use this when the agent holds its own credentials.
        execute_fn=False:           fn() is NOT called after approval.
                                    Use this when Token Vault executes the action
                                    server-side — avoids double execution.
                                    Returns {"status": "approved", "final_params": ...}.

        params_fn: optional callable that maps function arguments to the
                   approval params dict. If omitted, all kwargs are sent.
        """
        def decorator(fn: Callable) -> Callable:
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                params = self._resolve(fn, params_fn, args, kwargs)

                print(f"\n[ApprovalKit] Requesting approval: {connection}/{action}")
                print(f"             Params: {json.dumps(params)}")

                result = self._request_approval(connection, action, params)

                if result["status"] == "pre_approved":
                    print("[ApprovalKit] Pre-approved — executing immediately.")
                    if not execute_fn:
                        return {"status": "pre_approved", "final_params": params}
                    return fn(*args, **kwargs)

                if result["status"] == "blocked":
                    print("[ApprovalKit] Blocked by rule (blackout / policy).")
                    raise ApprovalDenied("blocked")

                job_id = result["job_id"]
                print(f"[ApprovalKit] Waiting for approval... (job={job_id})")
                print("[ApprovalKit] Push notification sent to approver's phone.")

                status, data = self._poll(job_id)

                if status == "approved":
                    final_params = data.get("final_params") or params
                    if execute_fn:
                        print("[ApprovalKit] Approved — executing function.")
                        return fn(*args, **kwargs)
                    else:
                        print("[ApprovalKit] Approved — Token Vault executed server-side.")
                        return {"status": "approved", "final_params": final_params}
                else:
                    print(f"[ApprovalKit] Approval {status} — function NOT executed.")
                    raise ApprovalDenied(status, job_id=job_id)

            return wrapper
        return decorator

    def gate(self, connection: str, action: str, params: dict) -> dict:
        """
        Inline approval gate — blocks until approved or raises ApprovalDenied.

        Returns the approval data dict (includes final_params if the approver
        modified the params before approving). Always use final_params for the
        actual action call to respect partial-approval changes:

            data = kit.gate("stripe-prod", "charge", {"amount": 100, "customer": "..."})
            stripe.charge(**(data.get("final_params") or {"amount": 100, ...}))
        """
        result = self._request_approval(connection, action, params)

        if result["status"] == "pre_approved":
            return {"status": "pre_approved", "final_params": params}
        if result["status"] == "blocked":
            raise ApprovalDenied("blocked")

        status, data = self._poll(result["job_id"])
        if status != "approved":
            raise ApprovalDenied(status, job_id=result["job_id"])
        return {"status": "approved", "final_params": data.get("final_params") or params}

    # ------------------------------------------------------------------
    # Async public API (wraps sync methods in a thread — no extra deps)
    # ------------------------------------------------------------------

    def async_requires_approval(
        self,
        connection: str,
        action: str,
        params_fn: Callable[..., dict] | None = None,
        execute_fn: bool = True,
    ):
        """
        Async version of requires_approval.
        Runs HMAC signing and HTTP polling in a thread pool so the event
        loop is not blocked during approval wait.

        Example:
            @kit.async_requires_approval("stripe-prod", "charge")
            async def charge_customer(amount: int, customer: str):
                await stripe.charge_async(amount=amount, customer=customer)
        """
        def decorator(fn: Callable) -> Callable:
            @functools.wraps(fn)
            async def wrapper(*args, **kwargs):
                params = self._resolve(fn, params_fn, args, kwargs)

                print(f"\n[ApprovalKit] Requesting approval: {connection}/{action}")
                print(f"             Params: {json.dumps(params)}")

                result = await asyncio.to_thread(
                    self._request_approval, connection, action, params
                )

                if result["status"] == "pre_approved":
                    print("[ApprovalKit] Pre-approved — executing immediately.")
                    if not execute_fn:
                        return {"status": "pre_approved", "final_params": params}
                    return await fn(*args, **kwargs) if asyncio.iscoroutinefunction(fn) else fn(*args, **kwargs)

                if result["status"] == "blocked":
                    print("[ApprovalKit] Blocked by rule (blackout / policy).")
                    raise ApprovalDenied("blocked")

                job_id = result["job_id"]
                print(f"[ApprovalKit] Waiting for approval... (job={job_id})")
                print("[ApprovalKit] Push notification sent to approver's phone.")

                status, data = await asyncio.to_thread(self._poll, job_id)

                if status == "approved":
                    final_params = data.get("final_params") or params
                    if execute_fn:
                        print("[ApprovalKit] Approved — executing function.")
                        return await fn(*args, **kwargs) if asyncio.iscoroutinefunction(fn) else fn(*args, **kwargs)
                    else:
                        print("[ApprovalKit] Approved — Token Vault executed server-side.")
                        return {"status": "approved", "final_params": final_params}
                else:
                    print(f"[ApprovalKit] Approval {status} — function NOT executed.")
                    raise ApprovalDenied(status, job_id=job_id)

            return wrapper
        return decorator

    async def async_gate(self, connection: str, action: str, params: dict) -> dict:
        """
        Async version of gate — awaitable, non-blocking for the event loop.

        Example:
            data = await kit.async_gate("stripe-prod", "charge", {"amount": 100})
            await stripe.charge_async(**(data.get("final_params") or params))
        """
        result = await asyncio.to_thread(self._request_approval, connection, action, params)

        if result["status"] == "pre_approved":
            return {"status": "pre_approved", "final_params": params}
        if result["status"] == "blocked":
            raise ApprovalDenied("blocked")

        status, data = await asyncio.to_thread(self._poll, result["job_id"])
        if status != "approved":
            raise ApprovalDenied(status, job_id=result["job_id"])
        return {"status": "approved", "final_params": data.get("final_params") or params}

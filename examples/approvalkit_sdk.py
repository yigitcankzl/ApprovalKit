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
    )

    @kit.requires_approval(connection="stripe-prod", action="charge")
    def charge_customer(amount: int, customer: str):
        # this code only runs after a human approves
        stripe.charge(amount=amount, customer=customer)
"""

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
        user_id: str = "auth0|agent",
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

    def _poll(self, job_id: str) -> str:
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            r = requests.get(
                f"{self.base_url}/api/v1/status/{job_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10,
            )
            status = r.json().get("status", "pending")
            if status in ("approved", "rejected", "timeout", "blocked"):
                return status
            time.sleep(self.poll_interval)
        return "timeout"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def requires_approval(
        self,
        connection: str,
        action: str,
        params_fn: Callable[..., dict] | None = None,
    ):
        """
        Decorator — gates the wrapped function behind a human approval.

        params_fn: optional callable that maps function arguments to the
                   approval params dict. If omitted, all kwargs are sent.

        Example:
            @kit.requires_approval(
                "stripe", "charge",
                params_fn=lambda amount, customer: {"amount": amount, "to": customer}
            )
            def charge(...): ...
        """
        def decorator(fn: Callable) -> Callable:
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                if params_fn:
                    params = params_fn(*args, **kwargs)
                else:
                    sig = inspect.signature(fn)
                    bound = sig.bind(*args, **kwargs)
                    bound.apply_defaults()
                    params = dict(bound.arguments)

                print(f"\n[ApprovalKit] Requesting approval: {connection}/{action}")
                print(f"             Params: {json.dumps(params)}")

                result = self._request_approval(connection, action, params)

                if result["status"] == "pre_approved":
                    print("[ApprovalKit] Pre-approved — executing immediately.")
                    return fn(*args, **kwargs)

                if result["status"] == "blocked":
                    print("[ApprovalKit] Blocked by rule (blackout / policy).")
                    raise ApprovalDenied("blocked")

                job_id = result["job_id"]
                print(f"[ApprovalKit] Waiting for approval... (job={job_id})")
                print("[ApprovalKit] Push notification sent to approver's phone.")

                final = self._poll(job_id)

                if final == "approved":
                    print("[ApprovalKit] Approved — executing function.")
                    return fn(*args, **kwargs)
                else:
                    print(f"[ApprovalKit] Approval {final} — function NOT executed.")
                    raise ApprovalDenied(final, job_id=job_id)

            return wrapper
        return decorator

    def gate(self, connection: str, action: str, params: dict) -> None:
        """
        Inline approval gate — use instead of the decorator when you need
        conditional logic before deciding to call the function.

        Raises ApprovalDenied if the request is rejected/timed out.

            kit.gate("stripe", "charge", {"amount": 100, "customer": "..."})
            # reaching this line means approved
            stripe.charge(...)
        """
        result = self._request_approval(connection, action, params)

        if result["status"] == "pre_approved":
            return
        if result["status"] == "blocked":
            raise ApprovalDenied("blocked")

        final = self._poll(result["job_id"])
        if final != "approved":
            raise ApprovalDenied(final, job_id=result["job_id"])

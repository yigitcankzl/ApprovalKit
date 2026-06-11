"""Python SDK client/server execution mode behavior.

These exercise the decorator/gate logic without real network I/O by
stubbing the SDK's request/poll helpers.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk"))

import pytest

from approvalkit import ApprovalKit, ApprovalDenied


def _kit(execution_mode="client"):
    return ApprovalKit(
        base_url="http://test",
        api_key="k",
        hmac_secret="s",
        user_id="t",
        execution_mode=execution_mode,
        poll_interval=1,
    )


def _stub_pending(kit, *, status="approved", final_params=None, reason=None):
    """Stub the network so a request goes pending then resolves to `status`."""
    kit._request_approval = lambda c, a, p: {"status": "pending", "job_id": "j1"}
    data = {}
    if final_params is not None:
        data["final_params"] = final_params
    if reason is not None:
        data["rejection_reason"] = reason
    kit._poll = lambda job_id: (status, data)


# ── construction ──────────────────────────────────────────────────────────────

def test_default_execution_mode_is_client():
    assert _kit().execution_mode == "client"


def test_invalid_execution_mode_raises():
    with pytest.raises(ValueError):
        ApprovalKit(execution_mode="hybrid")


# ── client mode: the SDK runs the user's function after approval ──────────────

def test_client_mode_runs_function_and_returns_its_value():
    kit = _kit("client")
    _stub_pending(kit, status="approved")

    @kit.requires_approval(connection="stripe", action="charge")
    def charge(amount, customer):
        return {"charged": amount, "to": customer}

    result = charge(amount=150, customer="alice@example.com")
    assert result == {"charged": 150, "to": "alice@example.com"}


def test_client_mode_applies_approver_modified_params():
    kit = _kit("client")
    _stub_pending(kit, status="approved", final_params={"amount": 50, "customer": "bob@example.com"})

    @kit.requires_approval(connection="stripe", action="charge")
    def charge(amount, customer):
        return {"charged": amount, "to": customer}

    # approver lowered the amount and changed the recipient
    result = charge(amount=150, customer="alice@example.com")
    assert result == {"charged": 50, "to": "bob@example.com"}


def test_client_mode_params_fn_does_not_auto_map(monkeypatch):
    """Advanced: with params_fn, modified final_params are NOT mapped back —
    the original args are passed through unchanged."""
    kit = _kit("client")
    _stub_pending(kit, status="approved", final_params={"amount": 999})

    @kit.requires_approval(
        connection="stripe", action="charge",
        params_fn=lambda order: {"amount": order["amt"]},
    )
    def charge(order):
        return order

    result = charge({"amt": 10, "id": "o1"})
    assert result == {"amt": 10, "id": "o1"}  # original order, not final_params


def test_client_mode_does_not_run_function_on_reject():
    kit = _kit("client")
    _stub_pending(kit, status="rejected", reason="too risky")
    calls = []

    @kit.requires_approval(connection="stripe", action="charge")
    def charge(amount):
        calls.append(amount)
        return amount

    with pytest.raises(ApprovalDenied):
        charge(amount=150)
    assert calls == []  # function never ran


# ── server mode: legacy — function body never runs ────────────────────────────

def test_server_mode_does_not_run_function():
    kit = _kit("server")
    _stub_pending(kit, status="approved", final_params={"amount": 150})
    calls = []

    @kit.requires_approval(connection="stripe", action="charge")
    def charge(amount):
        calls.append(amount)
        return "should not happen"

    result = charge(amount=150)
    assert calls == []  # server executes; fn body is ignored
    assert result["status"] == "approved"
    assert result["final_params"] == {"amount": 150}


# ── gate returns approval result only (never runs an action) ──────────────────

def test_gate_returns_approval_result_only():
    kit = _kit("client")
    _stub_pending(kit, status="approved", final_params={"amount": 75})
    result = kit.gate("stripe", "charge", {"amount": 75})
    assert result == {"status": "approved", "final_params": {"amount": 75}}


# ── async decorator runs the coroutine after approval (client mode) ───────────

def test_async_client_mode_runs_coroutine():
    kit = _kit("client")
    _stub_pending(kit, status="approved")

    @kit.async_requires_approval(connection="github", action="deploy")
    async def deploy(env, branch):
        return f"deployed {branch} to {env}"

    result = asyncio.run(deploy(env="prod", branch="main"))
    assert result == "deployed main to prod"


def test_async_server_mode_does_not_run_coroutine():
    kit = _kit("server")
    _stub_pending(kit, status="approved", final_params={"env": "prod"})
    calls = []

    @kit.async_requires_approval(connection="github", action="deploy")
    async def deploy(env, branch):
        calls.append(env)
        return "should not happen"

    result = asyncio.run(deploy(env="prod", branch="main"))
    assert calls == []
    assert result["status"] == "approved"

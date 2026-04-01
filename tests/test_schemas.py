"""Tests for Pydantic schema validation."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from pydantic import ValidationError
from api.schemas.request import ApprovalRequest


def test_valid_request():
    req = ApprovalRequest(
        connection="stripe-prod",
        action="charge",
        params={"amount": 340, "customer": "john@example.com"},
        user_id="auth0|abc123",
        idempotency_key="req-7f3a9b2c-1234",
    )
    assert req.connection == "stripe-prod"
    assert req.action == "charge"


def test_injection_safe_action():
    with pytest.raises(ValidationError):
        ApprovalRequest(
            connection="stripe",
            action="charge; DROP TABLE",
            params={},
            user_id="auth0|abc",
            idempotency_key="key1",
        )


def test_action_no_uppercase():
    with pytest.raises(ValidationError):
        ApprovalRequest(
            connection="stripe",
            action="Charge",
            params={},
            user_id="auth0|abc",
            idempotency_key="key1",
        )


def test_forbidden_params_key():
    with pytest.raises(ValidationError):
        ApprovalRequest(
            connection="stripe",
            action="charge",
            params={"__proto__": "malicious"},
            user_id="auth0|abc",
            idempotency_key="key1",
        )


def test_forbidden_constructor_key():
    with pytest.raises(ValidationError):
        ApprovalRequest(
            connection="stripe",
            action="charge",
            params={"constructor": "exploit"},
            user_id="auth0|abc",
            idempotency_key="key1",
        )


def test_user_id_accepts_any_provider():
    """user_id accepts any identity provider format (auth0|, google|, etc.)"""
    req = ApprovalRequest(
        connection="stripe",
        action="charge",
        params={},
        user_id="google|123",
        idempotency_key="key1",
    )
    assert req.user_id == "google|123"


def test_action_allows_colons():
    req = ApprovalRequest(
        connection="stripe",
        action="stripe:charge",
        params={},
        user_id="auth0|123",
        idempotency_key="key1",
    )
    assert req.action == "stripe:charge"


def test_action_allows_underscores():
    req = ApprovalRequest(
        connection="github",
        action="merge_pr",
        params={},
        user_id="auth0|123",
        idempotency_key="key1",
    )
    assert req.action == "merge_pr"

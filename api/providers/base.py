"""
Provider protocols.

These define the minimum surface every backend must implement. The
existing Auth0-specific service objects continue to exist; the
adapters in `api/providers/auth0` translate between them and the
protocols here.

Protocols (PEP 544) are used so existing duck-typed services can be
adopted without inheritance churn.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class ProviderUnavailable(RuntimeError):
    """Raised when the selected provider is unconfigured or unreachable."""


class ApprovalStatus(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    ERROR = "error"
    PENDING = "pending"


@dataclass(slots=True)
class ApprovalRequest:
    """A single human-approval ask handed to an ApprovalChannel."""
    user_id: str
    binding_message: str
    scope: str = "openid"
    job_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ApprovalResponse:
    """Terminal result of an approval request."""
    status: ApprovalStatus
    access_token: str | None = None
    source: str | None = None  # "ciba", "email", "web", ...
    error: str | None = None


@dataclass(slots=True)
class Identity:
    """The authenticated caller behind a request."""
    sub: str
    email: str | None = None
    name: str | None = None
    claims: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ApprovalChannel(Protocol):
    """How approvers are reached and how their decisions are collected.

    Implementations should be idempotent w.r.t. ``job_id`` — the
    pipeline may retry initiation if the worker crashes.
    """

    name: str

    async def initiate(self, request: ApprovalRequest) -> str:
        """Start an approval flow and return a channel-specific handle
        (e.g. CIBA auth_req_id or an email token id) used for polling.
        """
        ...

    async def poll(self, handle: str, *, timeout: int, job_id: str = "") -> ApprovalResponse:
        """Wait up to ``timeout`` seconds for a decision."""
        ...


@runtime_checkable
class CredentialStore(Protocol):
    """Where third-party credentials live and how they are vended.

    Returning credentials by exchange (Auth0 Token Vault) is preferred
    over returning long-lived secrets; for local development the local
    store simply decrypts a Fernet ciphertext.
    """

    name: str

    async def get_access_token(
        self,
        *,
        user_id: str,
        connection: str,
        scope: str | None = None,
    ) -> str:
        """Return a short-lived access token for ``connection``."""
        ...

    async def health_check(self, *, user_id: str, connection: str) -> bool:
        """Return True iff a usable credential exists for this user+connection."""
        ...


@runtime_checkable
class IdentityProvider(Protocol):
    """Authenticates incoming HTTP requests."""

    name: str

    async def authenticate(self, *, authorization: str | None, headers: dict[str, str]) -> Identity:
        """Resolve the calling identity or raise ``ProviderUnavailable``."""
        ...

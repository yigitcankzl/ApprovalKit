"""
Auth0 CIBA approval channel.

Thin adapter over the existing `CIBAService` (api/services/ciba.py).
The service object is kept as-is so the rest of the codebase keeps
working; this module exposes it through the ApprovalChannel protocol.
"""
from __future__ import annotations

from api.providers.base import (
    ApprovalChannel,
    ApprovalRequest,
    ApprovalResponse,
    ApprovalStatus,
    ProviderUnavailable,
)
from api.services.ciba import ciba_service


class Auth0CIBAChannel(ApprovalChannel):
    name = "auth0-ciba"

    async def initiate(self, request: ApprovalRequest) -> str:
        domain = request.metadata.get("auth0_domain", "")
        client_id = request.metadata.get("auth0_client_id", "")
        client_secret = request.metadata.get("auth0_client_secret", "")
        try:
            result = await ciba_service.initiate_ciba_request(
                user_id=request.user_id,
                binding_message=request.binding_message,
                scope=request.scope,
                domain=domain,
                client_id=client_id,
                client_secret=client_secret,
            )
        except RuntimeError as e:
            raise ProviderUnavailable(str(e)) from e
        auth_req_id = result.get("auth_req_id")
        if not auth_req_id:
            raise ProviderUnavailable("CIBA initiate returned no auth_req_id")
        return auth_req_id

    async def poll(self, handle: str, *, timeout: int, job_id: str = "") -> ApprovalResponse:
        result = await ciba_service.poll_ciba_token(
            auth_req_id=handle, timeout=timeout, job_id=job_id,
        )
        status_raw = result.get("status", "error")
        try:
            status = ApprovalStatus(status_raw)
        except ValueError:
            status = ApprovalStatus.ERROR
        return ApprovalResponse(
            status=status,
            access_token=result.get("access_token"),
            source=result.get("source"),
            error=result.get("error"),
        )

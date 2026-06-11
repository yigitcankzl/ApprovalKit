"""Auth0 Token Vault action executor.

Wraps the existing :mod:`api.services.token_vault` service behind the
``ActionExecutor`` protocol so server-side execution becomes swappable.
The behavior (credential exchange via Token Vault, execution receipts) is
unchanged — this is purely an adapter.
"""
from __future__ import annotations

from typing import Any

from api.providers.base import ActionExecutionRequest, ActionExecutor


class Auth0TokenVaultExecutor(ActionExecutor):
    name = "auth0-token-vault"

    async def execute(self, request: ActionExecutionRequest) -> dict[str, Any]:
        from api.services.token_vault import token_vault_service

        return await token_vault_service.execute_action(
            connection=request.connection,
            action=request.action,
            params=request.params,
            workspace_id=request.workspace_id,
            db=request.db,
            approver_auth0_id=request.approver_user_id,
        )

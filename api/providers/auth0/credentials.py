"""
Auth0 Token Vault credential store.

Adapts the existing `TokenVaultService.get_token_via_exchange` to the
generic `CredentialStore` protocol. Refresh-token lookup remains the
responsibility of the calling code (it lives in the Connection model)
— this adapter is invoked once the refresh token is in hand.

For most callers it is more convenient to keep using
`TokenVaultService.execute_action` directly, which performs the full
chain (refresh token lookup, exchange, HTTP call). The protocol here
exists so generic plumbing (e.g. health checks, new providers) can be
written against an abstraction.
"""
from __future__ import annotations

from typing import Any

from api.providers.base import CredentialStore, ProviderUnavailable
from api.services.token_vault import token_vault_service


class Auth0TokenVaultStore(CredentialStore):
    name = "auth0-token-vault"

    def __init__(
        self,
        *,
        refresh_token_lookup,
        workspace_credentials: dict[str, str] | None = None,
    ):
        """
        Args:
            refresh_token_lookup: ``async (user_id, connection) -> str`` resolving
                the Auth0 refresh token for the (user, connection) pair.
            workspace_credentials: Optional overrides for ``auth0_domain``,
                ``auth0_client_id``, ``auth0_client_secret`` (multi-tenant).
        """
        self._lookup = refresh_token_lookup
        self._creds = workspace_credentials or {}

    async def get_access_token(
        self, *, user_id: str, connection: str, scope: str | None = None,
    ) -> str:
        refresh_token = await self._lookup(user_id, connection)
        if not refresh_token:
            raise ProviderUnavailable(
                f"No Token Vault refresh token for {user_id}@{connection}"
            )
        token = await token_vault_service.get_token_via_exchange(
            connection_name=connection,
            refresh_token=refresh_token,
            domain=self._creds.get("auth0_domain", ""),
            client_id=self._creds.get("auth0_client_id", ""),
            client_secret=self._creds.get("auth0_client_secret", ""),
        )
        if not token:
            raise ProviderUnavailable(
                f"Token Vault exchange failed for {user_id}@{connection}"
            )
        return token

    async def health_check(self, *, user_id: str, connection: str) -> bool:
        try:
            await self.get_access_token(user_id=user_id, connection=connection)
        except ProviderUnavailable:
            return False
        return True

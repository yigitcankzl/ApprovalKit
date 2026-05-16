"""
Local credential store.

A Fernet-encrypted, file/DB-backed credential store for deployments
that don't use Auth0 Token Vault. Useful for local development,
self-hosted setups, and CI.

The store accepts a ``loader`` callable that returns the **already
encrypted** ciphertext for a given (user, connection) pair. It then
decrypts on demand using the existing `api.services.encryption`
module (Fernet, with key rotation support). Keeping the load function
external means callers can wire it to any storage layer — Postgres,
SQLite, the filesystem — without this module taking a DB dependency.
"""
from __future__ import annotations

from typing import Awaitable, Callable

from api.providers.base import CredentialStore, ProviderUnavailable
from api.services.encryption import decrypt_secret


CipherLoader = Callable[[str, str], Awaitable[str | None]]


class LocalCredentialStore(CredentialStore):
    name = "local-fernet"

    def __init__(self, loader: CipherLoader):
        """
        Args:
            loader: ``async (user_id, connection) -> str | None`` returning
                the encrypted access token (Fernet ciphertext) or None.
        """
        self._loader = loader

    async def get_access_token(
        self, *, user_id: str, connection: str, scope: str | None = None,
    ) -> str:
        ciphertext = await self._loader(user_id, connection)
        if not ciphertext:
            raise ProviderUnavailable(
                f"No local credential for {user_id}@{connection}"
            )
        plaintext = decrypt_secret(ciphertext)
        if not plaintext:
            raise ProviderUnavailable(
                f"Failed to decrypt local credential for {user_id}@{connection}"
            )
        return plaintext

    async def health_check(self, *, user_id: str, connection: str) -> bool:
        try:
            await self.get_access_token(user_id=user_id, connection=connection)
        except ProviderUnavailable:
            return False
        return True

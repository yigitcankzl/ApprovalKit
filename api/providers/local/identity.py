"""
Local header-based identity provider.

Trusts an ``X-User-Sub`` header. Intended for development, internal
tools behind a separate auth proxy, or test environments. Refuses to
operate when ``ENVIRONMENT=production``.
"""
from __future__ import annotations

from api.config import get_settings
from api.providers.base import Identity, IdentityProvider, ProviderUnavailable


class LocalHeaderIdentityProvider(IdentityProvider):
    name = "local-header"

    def __init__(self, *, allow_production: bool = False):
        self._allow_production = allow_production

    async def authenticate(
        self, *, authorization: str | None, headers: dict[str, str],
    ) -> Identity:
        if get_settings().ENVIRONMENT == "production" and not self._allow_production:
            raise ProviderUnavailable(
                "LocalHeaderIdentityProvider is disabled in production"
            )
        sub = (headers.get("x-user-sub") or headers.get("X-User-Sub") or "").strip()
        if not sub:
            raise ProviderUnavailable("Missing X-User-Sub header")
        return Identity(
            sub=sub,
            email=headers.get("x-user-email") or None,
            name=headers.get("x-user-name") or None,
        )

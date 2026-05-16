"""
Auth0 JWT identity provider.

Wraps the existing workspace middleware which already validates Auth0
access tokens via JWKS. This module exposes that logic through the
generic IdentityProvider protocol so non-Auth0 deployments can swap in
their own implementation without touching the route layer.
"""
from __future__ import annotations

from api.providers.base import Identity, IdentityProvider, ProviderUnavailable


class Auth0JWTIdentityProvider(IdentityProvider):
    name = "auth0-jwt"

    async def authenticate(
        self, *, authorization: str | None, headers: dict[str, str],
    ) -> Identity:
        # Import locally to avoid an import cycle with the FastAPI app.
        from api.middleware.workspace import _verify_auth0_token

        if not authorization or not authorization.startswith("Bearer "):
            raise ProviderUnavailable("Missing bearer token")
        token = authorization.removeprefix("Bearer ").strip()
        try:
            claims = await _verify_auth0_token(token)
        except Exception as e:  # noqa: BLE001 - propagate as ProviderUnavailable
            raise ProviderUnavailable(f"JWT verification failed: {e}") from e
        if not claims or not claims.get("sub"):
            raise ProviderUnavailable("JWT missing sub claim")
        return Identity(
            sub=claims["sub"],
            email=claims.get("email"),
            name=claims.get("name"),
            claims=claims,
        )

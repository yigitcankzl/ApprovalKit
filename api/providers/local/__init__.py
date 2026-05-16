"""Local (Auth0-less) providers for development and self-hosted deployments."""
from api.providers.local.approval import LocalApprovalChannel
from api.providers.local.credentials import LocalCredentialStore
from api.providers.local.identity import LocalHeaderIdentityProvider

__all__ = [
    "LocalApprovalChannel",
    "LocalCredentialStore",
    "LocalHeaderIdentityProvider",
]

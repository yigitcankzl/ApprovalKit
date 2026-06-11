"""
ApprovalKit provider abstraction.

ApprovalKit decouples three concerns behind protocols so the core
approval pipeline can run against different backends:

* `ApprovalChannel` — how a human is asked to approve a request and how
  the response is collected. Auth0 CIBA + Guardian is the default;
  email-link approvals or any custom transport can be plugged in.
* `CredentialStore` — where third-party credentials live and how they
  are exchanged for short-lived access tokens at execution time. Auth0
  Token Vault (RFC 8693) is the default; a Fernet-encrypted local
  store ships for development and self-hosted deployments without
  Auth0.
* `IdentityProvider` — who the calling user is. Auth0 JWTs are the
  default; a development "X-User-Sub" header provider exists for local
  use.

Concrete providers live in `api/providers/auth0` and
`api/providers/local`. The active providers are selected by
`APPROVAL_PROVIDER` (and individual overrides) in settings.
"""
from api.providers.base import (
    ActionExecutionRequest,
    ActionExecutor,
    ApprovalChannel,
    ApprovalRequest,
    ApprovalResponse,
    ApprovalStatus,
    CredentialStore,
    IdentityProvider,
    Identity,
    ProviderUnavailable,
)
from api.providers.factory import (
    get_action_executor,
    get_approval_channel,
    get_credential_store,
    get_identity_provider,
    reset_provider_cache,
)

__all__ = [
    "ActionExecutionRequest",
    "ActionExecutor",
    "ApprovalChannel",
    "ApprovalRequest",
    "ApprovalResponse",
    "ApprovalStatus",
    "CredentialStore",
    "IdentityProvider",
    "Identity",
    "ProviderUnavailable",
    "get_action_executor",
    "get_approval_channel",
    "get_credential_store",
    "get_identity_provider",
    "reset_provider_cache",
]

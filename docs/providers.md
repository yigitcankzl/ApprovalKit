# Providers

ApprovalKit ships two backends out of the box: **Auth0** (production
default) and **local** (development / self-hosted / CI). They are
selected via the `APPROVAL_PROVIDER` environment variable. Individual
components can be overridden independently.

## Selecting a backend

```env
# Easiest: pick a bundle.
APPROVAL_PROVIDER=auth0      # default
# or
APPROVAL_PROVIDER=local

# Optional per-component overrides:
APPROVAL_CHANNEL=local       # how humans are reached
CREDENTIAL_STORE=auth0       # where credentials live
IDENTITY_PROVIDER=local      # how callers are authenticated
```

The factory in [`api/providers/factory.py`](https://github.com/yigitcankzl/ApprovalKit/blob/main/api/providers/factory.py)
caches the resolved providers; call `reset_provider_cache()` from
tests that flip env vars.

## Backends compared

|                  | `auth0`                                    | `local`                                          |
|------------------|--------------------------------------------|--------------------------------------------------|
| Approval channel | CIBA push to Guardian app                  | Redis-backed handles, HTTP approve/reject        |
| Credential store | Token Vault (RFC 8693 Token Exchange)      | Fernet-encrypted tokens via a caller-supplied loader |
| Identity        | Auth0 JWT verification (JWKS)              | `X-User-Sub` header (refused in production)      |
| Auth0 required?  | yes                                        | no                                               |
| Best for         | production deployments                     | development, self-hosted setups, CI              |

## Protocols

All backends implement three Protocols defined in
[`api/providers/base.py`](https://github.com/yigitcankzl/ApprovalKit/blob/main/api/providers/base.py):

```python
class ApprovalChannel(Protocol):
    name: str
    async def initiate(self, request: ApprovalRequest) -> str: ...
    async def poll(self, handle: str, *, timeout: int, job_id: str = "")
        -> ApprovalResponse: ...

class CredentialStore(Protocol):
    name: str
    async def get_access_token(self, *, user_id: str, connection: str,
        scope: str | None = None) -> str: ...
    async def health_check(self, *, user_id: str, connection: str) -> bool: ...

class IdentityProvider(Protocol):
    name: str
    async def authenticate(self, *, authorization: str | None,
        headers: dict[str, str]) -> Identity: ...
```

Anything implementing these protocols is a valid provider — including
your own.

## Writing a custom provider

1. Create a new module under `api/providers/<name>/`.
2. Implement one or more of the three protocols.
3. Wire it into `api/providers/factory.py` by adding a branch in the
   matching `get_*` function. Keep the cache key (`@lru_cache`) so the
   factory continues to return a singleton.
4. Add tests in `tests/test_providers.py`.

### Examples of what custom providers might do

* **Approval channel**: route approval requests through Slack
  interactive messages, SMS, PagerDuty, or a custom incident response
  tool.
* **Credential store**: read short-lived tokens from AWS Secrets
  Manager, HashiCorp Vault, GCP Secret Manager, or any KMS-backed
  store.
* **Identity provider**: integrate with Keycloak, Cognito, Okta, or
  a corporate SSO that already terminates at your reverse proxy.

## Local backend details

### Approval channel

`api/providers/local/approval.py`. Stores pending requests in Redis
under a random URL-safe handle. Operators decide via:

```
GET  /local-approvals/{handle}          → inspect
POST /local-approvals/{handle}/approve
POST /local-approvals/{handle}/reject
```

Set `LOCAL_APPROVAL_AUTO_APPROVE=true` to short-circuit for unattended
runs. Never enable this in production.

### Credential store

`api/providers/local/credentials.py`. Constructor takes a `loader`
callable that returns the Fernet ciphertext for a (user, connection)
pair. The store uses the same `api.services.encryption` module the
rest of the codebase uses (Fernet with key-rotation support).

This separation keeps the store decoupled from any specific storage
layer. Wire it to Postgres, SQLite, or the filesystem as needed.

### Identity provider

`api/providers/local/identity.py`. Trusts the `X-User-Sub` header.
**Refuses to operate when `ENVIRONMENT=production`** so it can't be
accidentally left on in a production deployment.

## Auth0 backend details

The Auth0 adapters are thin wrappers over the existing service objects
(`api/services/ciba.py`, `api/services/token_vault.py`, and the
workspace JWT middleware). The legacy services are still used directly
by routes that haven't migrated to the protocol surface — both styles
coexist.

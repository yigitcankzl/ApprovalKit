# Security model

ApprovalKit's threat model assumes the AI agent is potentially
compromised, jailbroken, or hallucinating. The platform is designed so
that even a fully malicious agent cannot perform destructive actions
on its own.

## Principles

1. **The agent never holds credentials.** Tokens live in a credential
   store (Auth0 Token Vault by default; Fernet-encrypted local store
   for self-hosted setups) and are exchanged for short-lived access
   tokens at execution time.
2. **High-stakes actions require human approval.** A configurable rule
   engine decides which actions auto-approve, which require a single
   human, and which require quorum or sequential sign-offs.
3. **Authorization is centralised.** One workspace, one rule set, one
   audit trail. Replacing or revoking an agent is an O(1) operation.
4. **All decisions are logged and tamper-evident.** Audit entries are
   hash-chained so any retroactive edit invalidates the chain.

## Threat → control mapping

| Threat                                  | Control                                                                 |
|-----------------------------------------|-------------------------------------------------------------------------|
| Agent leaks API keys                    | Agent never receives them — credential store + token exchange.          |
| Prompt injection forces a bad action    | Rule engine + human approval + parameter validation before execution.   |
| Agent escalates scope over time         | Scope-creep detection (3× amount, first-time action) + re-authorization. |
| Replay of an old request                | HMAC + timestamp tolerance window.                                       |
| Compromised approver phone              | Step-up to `all_of_n` / `k_of_n` for high-risk amounts.                 |
| Tampered audit log                      | SHA-256 hash chain; any edit breaks subsequent hashes.                  |
| Multi-tenant data leak                  | Workspace scoping at the DB + middleware layer.                         |
| Auth0 outage cascades to the platform   | Redis-backed circuit breaker around Auth0 calls.                        |
| Long-running approval token left open   | Time-boxed approvals (`approval_expiry_seconds`).                       |

## Layers in depth

### Credential isolation

Every action is executed by ApprovalKit, not the agent. The agent
calls `kit.gate("stripe-prod", "charge", {...})` and never sees a
Stripe key. With the Auth0 backend, tokens are vended via RFC 8693
Token Exchange. With the local backend, they are decrypted at
execution time and never leave the worker process.

### HMAC signing

The SDK signs every request with a composite key (`hmac_secret:
api_key`) so revoking one agent invalidates only that agent's
signatures. Timestamps in the signed payload prevent replay outside
the 5-minute window.

### Encryption at rest

Workspace credentials and OAuth tokens are encrypted with Fernet
(AES-128-CBC + HMAC-SHA256). Key rotation is supported via
`CREDENTIALS_KEY_PREVIOUS` — decryption tries the current key first
and falls back to the previous one, allowing lazy re-encryption.

### Input validation

Before any handler runs, parameters are checked against patterns for
SQL injection, shell injection, path traversal, and script injection.
This catches both prompt-injection attacks and genuine LLM mistakes.

### Audit chain

Each audit entry includes the SHA-256 of the previous entry. Any
retroactive change breaks the chain. Exportable as JSON or CSV for
compliance reviews.

## Reporting vulnerabilities

If you find a security issue, please **do not** open a public GitHub
issue. Email the maintainer (see the repository's profile contact)
with a clear reproduction. A formal `SECURITY.md` with PGP key and
response SLA is planned.
